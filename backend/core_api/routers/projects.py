"""Project CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import Project

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    task_type: str   # classification, detection, instance_seg, semantic_seg
    description: Optional[str] = None
    org_id: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    task_type: str
    description: Optional[str]
    org_id: str
    created_at: str

    model_config = {"from_attributes": True}


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    if data.task_type not in ("classification", "detection", "instance_seg", "semantic_seg"):
        raise HTTPException(status_code=400, detail="Invalid task_type")
    project = Project(
        org_id=data.org_id,
        name=data.name,
        task_type=data.task_type,
        description=data.description,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        task_type=project.task_type,
        description=project.description,
        org_id=project.org_id,
        created_at=project.created_at.isoformat(),
    )


@router.get("")
async def list_projects(org_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.org_id == org_id))
    projects = result.scalars().all()
    return [
        {"id": p.id, "name": p.name, "task_type": p.task_type, "description": p.description,
         "created_at": p.created_at.isoformat()}
        for p in projects
    ]


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"id": project.id, "name": project.name, "task_type": project.task_type,
            "description": project.description, "org_id": project.org_id,
            "created_at": project.created_at.isoformat()}


@router.put("/{project_id}")
async def update_project(project_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for k, v in data.items():
        if hasattr(project, k):
            setattr(project, k, v)
    await db.commit()
    return {"id": project.id, "name": project.name}


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()
