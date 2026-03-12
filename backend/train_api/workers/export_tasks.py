"""Model export tasks: ONNX, TFLite, CoreML, OpenVINO, NCNN."""
import os
import tempfile
from celery.utils.log import get_task_logger

from train_api.workers.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="export_model", max_retries=2)
def export_model(self, model_version_id: str, fmt: str, quantization: str = "fp32"):
    """Export a trained model to the specified format."""
    from shared.db.models import ModelVersion
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from shared.config import get_settings
    from core_api.services.storage import download_file, upload_file

    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        mv = db.query(ModelVersion).filter(ModelVersion.id == model_version_id).first()
        if not mv:
            raise ValueError(f"ModelVersion {model_version_id} not found")

        # Download the PyTorch model
        model_data = download_file(mv.artifact_storage_key)

        with tempfile.TemporaryDirectory() as tmpdir:
            pt_path = os.path.join(tmpdir, "model.pt")
            with open(pt_path, "wb") as f:
                f.write(model_data)

            export_path = _export_model(pt_path, fmt, quantization, tmpdir)

            if export_path and os.path.exists(export_path):
                with open(export_path, "rb") as f:
                    exported_data = f.read()

                storage_key = f"models/{mv.project_id}/{model_version_id}/exported/model.{fmt}"
                upload_file(exported_data, storage_key, "application/octet-stream")

                # Update model version export artifacts
                if mv.export_artifacts is None:
                    mv.export_artifacts = {}
                mv.export_artifacts[fmt] = storage_key
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(mv, "export_artifacts")
                db.commit()

                logger.info(f"Exported model {model_version_id} to {fmt}")
                return storage_key

    except Exception as e:
        logger.error(f"Export failed for {model_version_id} -> {fmt}: {e}")
        raise
    finally:
        db.close()


def _export_model(pt_path: str, fmt: str, quantization: str, tmpdir: str) -> str:
    """Run the format-specific export and return the output file path."""
    if fmt == "onnx":
        return _to_onnx(pt_path, tmpdir)
    elif fmt == "tflite":
        return _to_tflite(pt_path, tmpdir, quantization)
    elif fmt == "coreml":
        return _to_coreml(pt_path, tmpdir)
    elif fmt == "openvino":
        return _to_openvino(pt_path, tmpdir)
    elif fmt == "torchscript":
        return _to_torchscript(pt_path, tmpdir)
    elif fmt == "ncnn":
        return _to_ncnn(pt_path, tmpdir)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")


def _to_onnx(pt_path: str, tmpdir: str) -> str:
    try:
        from ultralytics import YOLO
        model = YOLO(pt_path)
        model.export(format="onnx", opset=17, simplify=True, dynamic=False)
        onnx_path = pt_path.replace(".pt", ".onnx")
        return onnx_path if os.path.exists(onnx_path) else None
    except Exception as e:
        logger.warning(f"ONNX export via Ultralytics failed, trying torch.onnx: {e}")
        import torch
        import torch.onnx
        model = torch.load(pt_path, map_location="cpu")
        if hasattr(model, "model"):
            model = model.model
        model.eval()
        dummy = torch.zeros(1, 3, 640, 640)
        onnx_path = os.path.join(tmpdir, "model.onnx")
        torch.onnx.export(model, dummy, onnx_path, opset_version=17)
        return onnx_path


def _to_tflite(pt_path: str, tmpdir: str, quantization: str) -> str:
    try:
        from ultralytics import YOLO
        model = YOLO(pt_path)
        suffix = "-int8" if quantization == "int8" else ("-fp16" if quantization == "fp16" else "")
        model.export(format="tflite", int8=(quantization == "int8"), half=(quantization == "fp16"))
        tflite_path = pt_path.replace(".pt", f"_saved_model/model{suffix}.tflite")
        return tflite_path if os.path.exists(tflite_path) else None
    except Exception as e:
        logger.error(f"TFLite export failed: {e}")
        raise


def _to_coreml(pt_path: str, tmpdir: str) -> str:
    try:
        from ultralytics import YOLO
        model = YOLO(pt_path)
        model.export(format="coreml")
        mlpackage_path = pt_path.replace(".pt", ".mlpackage")
        return mlpackage_path if os.path.exists(mlpackage_path) else None
    except Exception as e:
        logger.error(f"CoreML export failed: {e}")
        raise


def _to_openvino(pt_path: str, tmpdir: str) -> str:
    try:
        from ultralytics import YOLO
        model = YOLO(pt_path)
        model.export(format="openvino")
        ov_dir = pt_path.replace(".pt", "_openvino_model")
        return ov_dir if os.path.exists(ov_dir) else None
    except Exception as e:
        logger.error(f"OpenVINO export failed: {e}")
        raise


def _to_torchscript(pt_path: str, tmpdir: str) -> str:
    try:
        from ultralytics import YOLO
        model = YOLO(pt_path)
        model.export(format="torchscript")
        ts_path = pt_path.replace(".pt", ".torchscript")
        return ts_path if os.path.exists(ts_path) else None
    except Exception as e:
        logger.error(f"TorchScript export failed: {e}")
        raise


def _to_ncnn(pt_path: str, tmpdir: str) -> str:
    try:
        from ultralytics import YOLO
        model = YOLO(pt_path)
        model.export(format="ncnn")
        ncnn_dir = pt_path.replace(".pt", "_ncnn_model")
        return ncnn_dir if os.path.exists(ncnn_dir) else None
    except Exception as e:
        logger.error(f"NCNN export failed: {e}")
        raise


@celery_app.task(bind=True, name="export_dataset", max_retries=2)
def export_dataset(self, version_id: str, fmt: str):
    """Export a dataset version to the specified format and upload to MinIO."""
    import asyncio
    from core_api.services.export import export_dataset_version
    from core_api.services.storage import upload_file, get_presigned_url
    from shared.db import AsyncSessionLocal
    from shared.db.models import DatasetVersion
    from sqlalchemy.orm.attributes import flag_modified
    from shared.config import get_settings

    settings = get_settings()

    async def _run():
        tmpdir = tempfile.mkdtemp(prefix="export_")
        try:
            async with AsyncSessionLocal() as db:
                zip_path = await export_dataset_version(version_id, fmt, db, tmpdir)
                with open(zip_path, "rb") as f:
                    zip_data = f.read()

                storage_key = f"exports/{version_id}/{fmt}/dataset.zip"
                upload_file(zip_data, storage_key, "application/zip", bucket="visionforge-exports")

                # Cache the export key on the version
                version = await db.get(DatasetVersion, version_id)
                if version:
                    if not version.export_cache:
                        version.export_cache = {}
                    version.export_cache[fmt] = storage_key
                    flag_modified(version, "export_cache")
                    await db.commit()

                download_url = get_presigned_url(storage_key, expires_seconds=3600, bucket="visionforge-exports")
                return download_url
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    url = asyncio.run(_run())
    return url
