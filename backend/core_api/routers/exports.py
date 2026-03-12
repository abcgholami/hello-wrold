"""Dataset export endpoints — triggers Celery export task."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import DatasetVersion
from core_api.services.storage import get_presigned_url

router = APIRouter()

SUPPORTED_FORMATS = ["coco", "yolo", "voc", "createml", "csv", "supervisely"]


class ExportRequest(BaseModel):
    format: str


@router.post("/{version_id}")
async def trigger_export(
    version_id: str,
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a dataset export. Returns task ID; client polls /exports/{version_id}/status."""
    if req.format not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported format. Choose: {SUPPORTED_FORMATS}")

    result = await db.execute(select(DatasetVersion).where(DatasetVersion.id == version_id))
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Check cache
    if version.export_cache and req.format in version.export_cache:
        cached_key = version.export_cache[req.format]
        return {
            "status": "ready",
            "download_url": get_presigned_url(cached_key, expires_seconds=3600, bucket="visionforge-exports"),
        }

    # Submit Celery task
    from train_api.workers.celery_app import celery_app
    task = celery_app.send_task(
        "export_dataset",
        args=[version_id, req.format],
        queue="export",
    )

    return {"status": "processing", "task_id": task.id}


@router.get("/{version_id}/status/{task_id}")
async def export_status(version_id: str, task_id: str):
    """Poll export task status."""
    from train_api.workers.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    if result.ready():
        if result.successful():
            return {"status": "ready", "download_url": result.result}
        return {"status": "failed", "error": str(result.result)}
    return {"status": "processing", "task_id": task_id}


@router.get("/augmentation/catalog")
async def augmentation_catalog():
    """Return the Albumentations transform catalog for the no-code UI."""
    from core_api.services.augmentation import get_catalog
    return get_catalog()
