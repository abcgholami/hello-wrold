"""Label class management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import LabelClass

router = APIRouter()


class LabelClassCreate(BaseModel):
    project_id: str
    name: str
    color: str = "#FF0000"
    parent_id: Optional[str] = None
    supercategory: Optional[str] = None


@router.get("")
async def list_label_classes(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LabelClass).where(LabelClass.project_id == project_id))
    classes = result.scalars().all()
    return [
        {"id": c.id, "name": c.name, "color": c.color, "parent_id": c.parent_id,
         "supercategory": c.supercategory}
        for c in classes
    ]


@router.post("", status_code=201)
async def create_label_class(data: LabelClassCreate, db: AsyncSession = Depends(get_db)):
    lc = LabelClass(
        project_id=data.project_id,
        name=data.name,
        color=data.color,
        parent_id=data.parent_id,
        supercategory=data.supercategory,
    )
    db.add(lc)
    await db.commit()
    await db.refresh(lc)
    return {"id": lc.id, "name": lc.name, "color": lc.color}


@router.put("/{class_id}")
async def update_label_class(class_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LabelClass).where(LabelClass.id == class_id))
    lc = result.scalar_one_or_none()
    if not lc:
        raise HTTPException(status_code=404, detail="Label class not found")
    for k, v in data.items():
        if hasattr(lc, k):
            setattr(lc, k, v)
    await db.commit()
    return {"id": lc.id, "name": lc.name, "color": lc.color}


@router.delete("/{class_id}", status_code=204)
async def delete_label_class(class_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LabelClass).where(LabelClass.id == class_id))
    lc = result.scalar_one_or_none()
    if not lc:
        raise HTTPException(status_code=404, detail="Label class not found")
    await db.delete(lc)
    await db.commit()
