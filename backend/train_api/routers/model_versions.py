"""Model registry endpoints: versioning, promotion, export."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import ModelVersion, TrainingJob

router = APIRouter()

EXPORT_FORMATS = ["onnx", "tflite", "coreml", "openvino", "ncnn", "torchscript"]
STAGES = ["development", "staging", "production", "archived"]


class ModelVersionCreate(BaseModel):
    project_id: str
    training_job_id: Optional[str] = None
    architecture: str
    task_type: str
    name: Optional[str] = None
    description: Optional[str] = None
    artifact_storage_key: str
    metrics: Optional[dict] = None


class PromoteRequest(BaseModel):
    stage: str


class ExportRequest(BaseModel):
    format: str
    quantization: Optional[str] = "fp32"  # fp32, fp16, int8


@router.get("")
async def list_model_versions(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ModelVersion)
        .where(ModelVersion.project_id == project_id)
        .order_by(desc(ModelVersion.created_at))
    )
    versions = result.scalars().all()
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "name": v.name,
            "architecture": v.architecture,
            "task_type": v.task_type,
            "stage": v.stage,
            "is_champion": v.is_champion,
            "metrics": v.metrics,
            "export_artifacts": v.export_artifacts,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@router.get("/{version_id}")
async def get_model_version(version_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Model version not found")
    return {
        "id": v.id,
        "project_id": v.project_id,
        "training_job_id": v.training_job_id,
        "version_number": v.version_number,
        "name": v.name,
        "description": v.description,
        "architecture": v.architecture,
        "task_type": v.task_type,
        "stage": v.stage,
        "is_champion": v.is_champion,
        "metrics": v.metrics,
        "hyperparameters": v.hyperparameters,
        "artifact_storage_key": v.artifact_storage_key,
        "export_artifacts": v.export_artifacts,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.post("/{version_id}/promote")
async def promote_model_version(
    version_id: str,
    req: PromoteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Promote model to staging or production. Production sets is_champion=True."""
    if req.stage not in STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Choose: {STAGES}")

    result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Model version not found")

    v.stage = req.stage

    if req.stage == "production":
        # Demote previous champion
        prev_result = await db.execute(
            select(ModelVersion)
            .where(ModelVersion.project_id == v.project_id)
            .where(ModelVersion.is_champion == True)
            .where(ModelVersion.id != version_id)
        )
        for prev in prev_result.scalars().all():
            prev.is_champion = False
        v.is_champion = True

    await db.commit()
    return {"id": version_id, "stage": v.stage, "is_champion": v.is_champion}


@router.post("/{version_id}/export")
async def export_model(
    version_id: str,
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger model export to a target format (ONNX, TFLite, CoreML, etc.)."""
    if req.format not in EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported format. Choose: {EXPORT_FORMATS}")

    result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Model version not found")

    # Check if already exported
    if v.export_artifacts and req.format in v.export_artifacts:
        return {
            "status": "already_exported",
            "format": req.format,
            "storage_key": v.export_artifacts[req.format],
        }

    try:
        from train_api.workers.celery_app import celery_app
        task = celery_app.send_task(
            "export_model",
            args=[version_id, req.format, req.quantization],
            queue="default",
        )
        return {"status": "queued", "task_id": task.id, "format": req.format}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue export: {str(e)}")


@router.delete("/{version_id}")
async def delete_model_version(version_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Model version not found")
    if v.stage == "production":
        raise HTTPException(status_code=400, detail="Cannot delete a production model. Archive it first.")
    await db.delete(v)
    await db.commit()
    return {"deleted": version_id}
