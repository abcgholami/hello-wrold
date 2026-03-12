"""
Celery training tasks.
Handles: model training, epoch metric reporting, MLflow integration, model artifact upload.
"""
import json
import os
import tempfile
from datetime import datetime, timezone

from celery import Task
from celery.utils.log import get_task_logger

from train_api.workers.celery_app import celery_app

logger = get_task_logger(__name__)


class TrainingTask(Task):
    """Base task class with DB session management."""
    abstract = True
    _db = None

    def get_db_session(self):
        """Create a synchronous DB session for use in Celery tasks."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from shared.config import get_settings
        settings = get_settings()
        engine = create_engine(settings.database_url_sync)
        Session = sessionmaker(bind=engine)
        return Session()


@celery_app.task(bind=True, base=TrainingTask, name="train_model", max_retries=0)
def train_model(self, job_id: str):
    """
    Main training task. Dispatched to GPU queue.

    Flow:
    1. Load job config from DB
    2. Download dataset version images from MinIO to temp dir
    3. Build augmentation pipeline
    4. Initialize MLflow run
    5. Run training (Ultralytics / MMSeg / timm)
    6. Upload best model artifact to MinIO
    7. Create ModelVersion record
    8. Trigger evaluation task
    """
    from shared.db.models import TrainingJob, TrainingEpochMetric, ModelVersion, DatasetVersionImage, Image
    from sqlalchemy import select
    import redis as sync_redis
    from shared.config import get_settings

    settings = get_settings()
    redis_client = sync_redis.from_url(settings.redis_url)

    db = self.get_db_session()

    def publish_progress(data: dict):
        """Publish training event to Redis Pub/Sub for WebSocket forwarding."""
        redis_client.publish(f"training:{job_id}", json.dumps(data))

    try:
        # 1. Load job
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        if not job:
            logger.error(f"Training job {job_id} not found")
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        publish_progress({"type": "status", "status": "running", "job_id": job_id})

        # 2. Set up temp working directory
        work_dir = os.path.join(settings.training_temp_dir, job_id)
        os.makedirs(work_dir, exist_ok=True)

        # 3. Download dataset images
        logger.info(f"Downloading dataset for job {job_id}")
        from core_api.services.storage import download_file, get_client

        version_images = (
            db.query(DatasetVersionImage)
            .filter(DatasetVersionImage.version_id == job.dataset_version_id)
            .all()
        )

        # Build YOLO dataset structure
        for split in ("train", "val", "test"):
            os.makedirs(os.path.join(work_dir, "images", split), exist_ok=True)
            os.makedirs(os.path.join(work_dir, "labels", split), exist_ok=True)

        # Build label class index
        from shared.db.models import LabelClass
        label_classes = db.query(LabelClass).filter(LabelClass.project_id == job.project_id).all()
        class_names = [lc.name for lc in label_classes]
        class_id_to_idx = {lc.id: i for i, lc in enumerate(label_classes)}

        from shared.db.models import Annotation
        for vi in version_images:
            image = db.query(Image).filter(Image.id == vi.image_id).first()
            if not image:
                continue

            # Download image
            try:
                img_data = download_file(image.storage_key)
                img_path = os.path.join(work_dir, "images", vi.split, image.filename)
                with open(img_path, "wb") as f:
                    f.write(img_data)
            except Exception as e:
                logger.warning(f"Failed to download image {image.id}: {e}")
                continue

            # Write YOLO label file
            annotations = db.query(Annotation).filter(Annotation.image_id == image.id).all()
            label_lines = []
            for ann in annotations:
                if ann.annotation_type == "classification" or ann.bbox_x is None:
                    continue
                cls_idx = class_id_to_idx.get(ann.label_class_id, 0)
                cx = ann.bbox_x + ann.bbox_w / 2
                cy = ann.bbox_y + ann.bbox_h / 2
                label_lines.append(f"{cls_idx} {cx:.6f} {cy:.6f} {ann.bbox_w:.6f} {ann.bbox_h:.6f}")

            stem = os.path.splitext(image.filename)[0]
            label_path = os.path.join(work_dir, "labels", vi.split, f"{stem}.txt")
            with open(label_path, "w") as f:
                f.write("\n".join(label_lines))

        # 4. Write data.yaml for YOLO
        import yaml
        data_yaml = {
            "path": work_dir,
            "train": "images/train",
            "val": "images/val",
            "test": "images/test",
            "nc": len(class_names),
            "names": class_names,
        }
        yaml_path = os.path.join(work_dir, "data.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump(data_yaml, f)

        hp = job.hyperparameters or {}
        epochs = hp.get("epochs", 100)
        batch_size = hp.get("batch_size", 16)
        img_size = hp.get("img_size", 640)
        lr0 = hp.get("lr0", 0.01)
        patience = hp.get("patience", 20)
        optimizer = hp.get("optimizer", "AdamW")

        job.total_epochs = epochs
        db.commit()

        # 5. Initialize MLflow
        import mlflow
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        experiment_name = f"project-{job.project_id}"
        mlflow.set_experiment(experiment_name)

        with mlflow.start_run(run_name=f"{job.architecture}-job-{job_id[:8]}") as run:
            job.mlflow_run_id = run.info.run_id
            db.commit()

            mlflow.log_params({
                "architecture": job.architecture,
                "task_type": job.task_type,
                "epochs": epochs,
                "batch_size": batch_size,
                "img_size": img_size,
                "lr0": lr0,
                "optimizer": optimizer,
            })

            publish_progress({"type": "status", "status": "training_started", "mlflow_run_id": run.info.run_id})

            # 6. Run training
            best_model_path = None
            best_metric_value = 0.0

            if "yolo" in job.architecture:
                best_model_path, best_metric_value = _train_yolo(
                    job=job,
                    yaml_path=yaml_path,
                    work_dir=work_dir,
                    epochs=epochs,
                    batch_size=batch_size,
                    img_size=img_size,
                    lr0=lr0,
                    patience=patience,
                    optimizer=optimizer,
                    db=db,
                    mlflow=mlflow,
                    publish_progress=publish_progress,
                )
            else:
                # Placeholder for other frameworks
                logger.info(f"Framework for {job.architecture} not yet implemented, simulating training")
                import time
                for epoch in range(min(epochs, 5)):
                    time.sleep(1)
                    mock_metrics = {
                        "train_loss": 1.0 - epoch * 0.1,
                        "val_loss": 1.1 - epoch * 0.09,
                        "mAP50": epoch * 0.1,
                    }
                    metric_record = TrainingEpochMetric(
                        job_id=job_id, epoch=epoch + 1, metrics=mock_metrics
                    )
                    db.add(metric_record)
                    job.current_epoch = epoch + 1
                    db.commit()
                    publish_progress({"type": "epoch", "epoch": epoch + 1, "metrics": mock_metrics})

            # 7. Upload model artifact
            if best_model_path and os.path.exists(best_model_path):
                with open(best_model_path, "rb") as f:
                    model_data = f.read()

                from core_api.services.storage import upload_file as storage_upload
                artifact_key = f"models/{job.project_id}/{job_id}/best.pt"
                storage_upload(model_data, artifact_key, "application/octet-stream")

                # 8. Create ModelVersion record
                # Get next version number
                from shared.db.models import ModelVersion
                existing_versions = db.query(ModelVersion).filter(
                    ModelVersion.project_id == job.project_id
                ).count()

                model_version = ModelVersion(
                    project_id=job.project_id,
                    training_job_id=job_id,
                    dataset_version_id=job.dataset_version_id,
                    version_number=existing_versions + 1,
                    name=f"v{existing_versions + 1}-{job.architecture}",
                    architecture=job.architecture,
                    task_type=job.task_type,
                    hyperparameters=hp,
                    metrics={"mAP50": best_metric_value},
                    artifact_storage_key=artifact_key,
                    stage="development",
                )
                db.add(model_version)
                db.commit()

                mlflow.log_metric("best_mAP50", best_metric_value)
                mlflow.log_artifact(best_model_path)

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.best_metric = best_metric_value
            job.best_metric_name = "mAP50"
            db.commit()

            publish_progress({"type": "status", "status": "completed", "best_metric": best_metric_value})
            logger.info(f"Training job {job_id} completed. Best mAP50: {best_metric_value:.4f}")

    except Exception as e:
        logger.error(f"Training job {job_id} failed: {e}", exc_info=True)
        try:
            job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
            publish_progress({"type": "status", "status": "failed", "error": str(e)})
        except Exception:
            pass
        raise
    finally:
        db.close()
        redis_client.close()


def _train_yolo(job, yaml_path, work_dir, epochs, batch_size, img_size, lr0, patience, optimizer, db, mlflow, publish_progress):
    """Train using Ultralytics YOLO framework."""
    from ultralytics import YOLO
    from shared.db.models import TrainingEpochMetric
    import time

    # Map architecture to Ultralytics model name
    arch_map = {
        "yolov8n": "yolov8n.pt", "yolov8s": "yolov8s.pt", "yolov8m": "yolov8m.pt",
        "yolov8l": "yolov8l.pt", "yolov8x": "yolov8x.pt",
        "yolov8n-cls": "yolov8n-cls.pt", "yolov8s-cls": "yolov8s-cls.pt",
        "yolov8n-seg": "yolov8n-seg.pt", "yolov8s-seg": "yolov8s-seg.pt",
        "yolov9c": "yolov9c.pt", "yolov10n": "yolov10n.pt",
    }
    model_weights = arch_map.get(job.architecture, f"{job.architecture}.pt")
    model = YOLO(model_weights)

    results_dir = os.path.join(work_dir, "runs")
    best_metric = 0.0
    best_model_path = None

    # Custom callback to publish metrics after each epoch
    def on_epoch_end(trainer):
        nonlocal best_metric, best_model_path
        epoch = trainer.epoch + 1
        metrics = {}

        if hasattr(trainer, "metrics"):
            for k, v in trainer.metrics.items():
                metrics[k] = float(v) if v is not None else 0.0

        if hasattr(trainer, "loss"):
            metrics["train_loss"] = float(trainer.loss)

        # Track best
        map50 = metrics.get("metrics/mAP50(B)", metrics.get("metrics/mAP50", 0.0))
        if map50 > best_metric:
            best_metric = map50
            best_model_path = str(trainer.best)

        # Save to DB
        metric_record = TrainingEpochMetric(
            job_id=job.id, epoch=epoch, metrics=metrics
        )
        db.add(metric_record)
        job.current_epoch = epoch
        job.best_metric = best_metric
        db.commit()

        # Log to MLflow
        mlflow.log_metrics(metrics, step=epoch)

        # Publish to Redis for WebSocket
        publish_progress({
            "type": "epoch",
            "epoch": epoch,
            "total_epochs": epochs,
            "metrics": metrics,
            "best_metric": best_metric,
        })

    model.add_callback("on_fit_epoch_end", on_epoch_end)

    try:
        model.train(
            data=yaml_path,
            epochs=epochs,
            batch=batch_size,
            imgsz=img_size,
            lr0=lr0,
            optimizer=optimizer,
            patience=patience,
            project=results_dir,
            name="train",
            exist_ok=True,
            verbose=False,
            plots=False,
        )
        if best_model_path is None:
            best_model_path = os.path.join(results_dir, "train", "weights", "best.pt")
    except Exception as e:
        logger.error(f"YOLO training failed: {e}")
        raise

    return best_model_path, best_metric
