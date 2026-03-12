"""Training job management endpoints with real-time progress."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import TrainingJob, TrainingEpochMetric, DatasetVersion, Project

router = APIRouter()

VALID_ARCHITECTURES = {
    "classification": ["yolov8n-cls", "yolov8s-cls", "yolov8m-cls", "efficientnet-b0", "efficientnet-b4", "resnet50"],
    "detection": ["yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x", "yolov9c", "yolov10n", "yolov10s"],
    "instance_seg": ["yolov8n-seg", "yolov8s-seg", "yolov8m-seg", "yolov8l-seg"],
    "semantic_seg": ["segformer-b0", "segformer-b2", "segformer-b4", "deeplabv3plus"],
}

HYPERPARAMETER_PRESETS = {
    "fast": {"epochs": 30, "batch_size": 16, "img_size": 416, "optimizer": "SGD", "lr0": 0.01, "patience": 10, "augment": True},
    "balanced": {"epochs": 100, "batch_size": 16, "img_size": 640, "optimizer": "AdamW", "lr0": 0.001, "patience": 20, "augment": True},
    "accuracy": {"epochs": 300, "batch_size": 8, "img_size": 1280, "optimizer": "AdamW", "lr0": 0.0005, "patience": 50, "augment": True, "multi_scale": True},
}


class TrainingJobCreate(BaseModel):
    project_id: str
    dataset_version_id: str
    task_type: str
    architecture: str
    preset: Optional[str] = "balanced"
    hyperparameters: Optional[dict] = None
    name: Optional[str] = None


class TrainingJobResponse(BaseModel):
    id: str
    project_id: str
    status: str
    task_type: str
    architecture: str
    current_epoch: int
    total_epochs: int
    best_metric: Optional[float]
    best_metric_name: Optional[str]
    created_at: str


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_training_job(data: TrainingJobCreate, db: AsyncSession = Depends(get_db)):
    """Create and queue a training job."""
    # Validate task type
    if data.task_type not in VALID_ARCHITECTURES:
        raise HTTPException(status_code=400, detail=f"Invalid task_type. Choose: {list(VALID_ARCHITECTURES)}")

    # Validate architecture for task type
    if data.architecture not in VALID_ARCHITECTURES[data.task_type]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid architecture for {data.task_type}. Choose: {VALID_ARCHITECTURES[data.task_type]}"
        )

    # Verify dataset version exists
    version_result = await db.execute(select(DatasetVersion).where(DatasetVersion.id == data.dataset_version_id))
    version = version_result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Merge preset + custom hyperparameters
    hp = dict(HYPERPARAMETER_PRESETS.get(data.preset or "balanced", HYPERPARAMETER_PRESETS["balanced"]))
    if data.hyperparameters:
        hp.update(data.hyperparameters)

    job = TrainingJob(
        project_id=data.project_id,
        dataset_version_id=data.dataset_version_id,
        task_type=data.task_type,
        framework="ultralytics" if "yolo" in data.architecture else ("timm" if "efficientnet" in data.architecture or "resnet" in data.architecture else "mmseg"),
        architecture=data.architecture,
        hyperparameters=hp,
        preset=data.preset,
        total_epochs=hp.get("epochs", 100),
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch Celery task
    try:
        from train_api.workers.celery_app import celery_app
        task = celery_app.send_task("train_model", args=[job.id], queue="gpu_training")
        job.celery_task_id = task.id
        await db.commit()
    except Exception as e:
        # Even if Celery dispatch fails, job is saved — can be retried
        pass

    return {
        "id": job.id,
        "status": job.status,
        "task_type": job.task_type,
        "architecture": job.architecture,
        "hyperparameters": job.hyperparameters,
        "created_at": job.created_at.isoformat(),
    }


@router.get("")
async def list_training_jobs(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TrainingJob)
        .where(TrainingJob.project_id == project_id)
        .order_by(desc(TrainingJob.created_at))
    )
    jobs = result.scalars().all()
    return [
        {
            "id": j.id,
            "status": j.status,
            "task_type": j.task_type,
            "architecture": j.architecture,
            "current_epoch": j.current_epoch,
            "total_epochs": j.total_epochs,
            "best_metric": j.best_metric,
            "best_metric_name": j.best_metric_name,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]


@router.get("/{job_id}")
async def get_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    return {
        "id": job.id,
        "project_id": job.project_id,
        "dataset_version_id": job.dataset_version_id,
        "status": job.status,
        "task_type": job.task_type,
        "architecture": job.architecture,
        "framework": job.framework,
        "hyperparameters": job.hyperparameters,
        "preset": job.preset,
        "current_epoch": job.current_epoch,
        "total_epochs": job.total_epochs,
        "best_metric": job.best_metric,
        "best_metric_name": job.best_metric_name,
        "mlflow_run_id": job.mlflow_run_id,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/{job_id}/metrics")
async def get_job_metrics(job_id: str, db: AsyncSession = Depends(get_db)):
    """Return epoch-by-epoch metrics for the live loss curve."""
    result = await db.execute(
        select(TrainingEpochMetric)
        .where(TrainingEpochMetric.job_id == job_id)
        .order_by(TrainingEpochMetric.epoch)
    )
    metrics = result.scalars().all()
    return [
        {"epoch": m.epoch, "metrics": m.metrics, "logged_at": m.logged_at.isoformat() if m.logged_at else None}
        for m in metrics
    ]


@router.post("/{job_id}/cancel")
async def cancel_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    if job.status not in ("queued", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in status: {job.status}")

    # Revoke Celery task if exists
    if job.celery_task_id:
        try:
            from train_api.workers.celery_app import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True)
        except Exception:
            pass

    job.status = "cancelled"
    await db.commit()
    return {"id": job.id, "status": "cancelled"}


@router.get("/presets/list")
async def list_presets():
    """Return available hyperparameter presets for the wizard."""
    return HYPERPARAMETER_PRESETS


@router.get("/architectures/list")
async def list_architectures():
    """Return available model architectures by task type."""
    return VALID_ARCHITECTURES
