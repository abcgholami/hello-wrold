"""Project CRUD endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import Project

router = APIRouter()

VALID_TASK_TYPES = ("classification", "detection", "instance_seg", "semantic_seg")


class ProjectCreate(BaseModel):
    name: str
    task_type: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    if data.task_type not in VALID_TASK_TYPES:
        raise HTTPException(status_code=400, detail="Invalid task_type")
    project = Project(name=data.name, task_type=data.task_type, description=data.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return {"id": project.id, "name": project.name, "task_type": project.task_type,
            "description": project.description, "created_at": project.created_at.isoformat()}


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project))
    projects = result.scalars().all()
    return [{"id": p.id, "name": p.name, "task_type": p.task_type, "description": p.description,
             "created_at": p.created_at.isoformat()} for p in projects]


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"id": project.id, "name": project.name, "task_type": project.task_type,
            "description": project.description, "created_at": project.created_at.isoformat()}


@router.put("/{project_id}")
async def update_project(project_id: str, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for k, v in data.model_dump(exclude_none=True).items():
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
