"""Inference endpoint management."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import InferenceEndpoint, ModelVersion

router = APIRouter()


class EndpointCreate(BaseModel):
    project_id: str
    model_version_id: str
    name: str
    endpoint_type: str = "rest"
    config: Optional[dict] = None


class EndpointUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    config: Optional[dict] = None


@router.post("", status_code=201)
async def create_endpoint(data: EndpointCreate, db: AsyncSession = Depends(get_db)):
    # Verify model version exists
    mv_result = await db.execute(select(ModelVersion).where(ModelVersion.id == data.model_version_id))
    mv = mv_result.scalar_one_or_none()
    if not mv:
        raise HTTPException(status_code=404, detail="Model version not found")

    endpoint = InferenceEndpoint(
        project_id=data.project_id,
        model_version_id=data.model_version_id,
        name=data.name,
        endpoint_type=data.endpoint_type,
        config=data.config or {"confidence_threshold": 0.25, "iou_threshold": 0.45},
        status="active",
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)

    return {
        "id": endpoint.id,
        "name": endpoint.name,
        "project_id": endpoint.project_id,
        "model_version_id": endpoint.model_version_id,
        "status": endpoint.status,
        "config": endpoint.config,
        "created_at": endpoint.created_at.isoformat() if endpoint.created_at else None,
    }


@router.get("")
async def list_endpoints(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InferenceEndpoint).where(InferenceEndpoint.project_id == project_id)
    )
    endpoints = result.scalars().all()
    return [
        {
            "id": e.id,
            "name": e.name,
            "model_version_id": e.model_version_id,
            "status": e.status,
            "endpoint_type": e.endpoint_type,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in endpoints
    ]


@router.get("/{endpoint_id}")
async def get_endpoint(endpoint_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InferenceEndpoint).where(InferenceEndpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return {
        "id": endpoint.id,
        "name": endpoint.name,
        "project_id": endpoint.project_id,
        "model_version_id": endpoint.model_version_id,
        "status": endpoint.status,
        "endpoint_type": endpoint.endpoint_type,
        "config": endpoint.config,
        "created_at": endpoint.created_at.isoformat() if endpoint.created_at else None,
    }


@router.patch("/{endpoint_id}")
async def update_endpoint(endpoint_id: str, data: EndpointUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InferenceEndpoint).where(InferenceEndpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    if data.name is not None:
        endpoint.name = data.name
    if data.status is not None:
        if data.status not in ("active", "inactive"):
            raise HTTPException(status_code=400, detail="Invalid status")
        endpoint.status = data.status
    if data.config is not None:
        endpoint.config = data.config

    await db.commit()
    return {"id": endpoint.id, "status": endpoint.status}


@router.delete("/{endpoint_id}", status_code=204)
async def delete_endpoint(endpoint_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InferenceEndpoint).where(InferenceEndpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    await db.delete(endpoint)
    await db.commit()
