"""Annotation CRUD endpoints with support for all annotation types."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.db import get_db
from shared.db.models import Annotation, Image

router = APIRouter()


class AnnotationCreate(BaseModel):
    label_class_id: str
    annotation_type: str          # bbox, polygon, mask, classification, keypoints
    bbox_x: Optional[float] = None
    bbox_y: Optional[float] = None
    bbox_w: Optional[float] = None
    bbox_h: Optional[float] = None
    segmentation: Optional[Any] = None   # [[x1,y1,x2,y2,...]]
    keypoints: Optional[Any] = None
    confidence: float = 1.0
    is_ai_generated: bool = False


class AnnotationUpdate(BaseModel):
    label_class_id: Optional[str] = None
    bbox_x: Optional[float] = None
    bbox_y: Optional[float] = None
    bbox_w: Optional[float] = None
    bbox_h: Optional[float] = None
    segmentation: Optional[Any] = None
    keypoints: Optional[Any] = None
    review_status: Optional[str] = None  # pending, approved, rejected


def _serialize(ann: Annotation) -> dict:
    return {
        "id": ann.id,
        "image_id": ann.image_id,
        "label_class_id": ann.label_class_id,
        "annotation_type": ann.annotation_type,
        "bbox": [ann.bbox_x, ann.bbox_y, ann.bbox_w, ann.bbox_h] if ann.bbox_x is not None else None,
        "segmentation": ann.segmentation,
        "keypoints": ann.keypoints,
        "confidence": ann.confidence,
        "is_ai_generated": ann.is_ai_generated,
        "review_status": ann.review_status,
        "created_at": ann.created_at.isoformat() if ann.created_at else None,
    }


@router.get("/images/{image_id}/annotations")
async def list_annotations(image_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Annotation)
        .where(Annotation.image_id == image_id)
        .options(selectinload(Annotation.label_class))
    )
    annotations = result.scalars().all()
    return [_serialize(a) for a in annotations]


@router.post("/images/{image_id}/annotations", status_code=201)
async def create_annotation(
    image_id: str,
    data: AnnotationCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Image).where(Image.id == image_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Image not found")

    ann = Annotation(
        image_id=image_id,
        label_class_id=data.label_class_id,
        annotation_type=data.annotation_type,
        bbox_x=data.bbox_x,
        bbox_y=data.bbox_y,
        bbox_w=data.bbox_w,
        bbox_h=data.bbox_h,
        segmentation=data.segmentation,
        keypoints=data.keypoints,
        confidence=data.confidence,
        is_ai_generated=data.is_ai_generated,
    )
    db.add(ann)

    # Update image annotation_status
    img_result = await db.execute(select(Image).where(Image.id == image_id))
    img = img_result.scalar_one_or_none()
    if img and img.annotation_status == "unannotated":
        img.annotation_status = "in_progress"

    await db.commit()
    await db.refresh(ann)
    return _serialize(ann)


@router.post("/images/{image_id}/annotations/batch", status_code=201)
async def create_annotations_batch(
    image_id: str,
    data: List[AnnotationCreate],
    db: AsyncSession = Depends(get_db),
):
    """Create multiple annotations at once (used after AI-assist bulk predict)."""
    result = await db.execute(select(Image).where(Image.id == image_id))
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    created = []
    for item in data:
        ann = Annotation(
            image_id=image_id,
            label_class_id=item.label_class_id,
            annotation_type=item.annotation_type,
            bbox_x=item.bbox_x,
            bbox_y=item.bbox_y,
            bbox_w=item.bbox_w,
            bbox_h=item.bbox_h,
            segmentation=item.segmentation,
            keypoints=item.keypoints,
            confidence=item.confidence,
            is_ai_generated=item.is_ai_generated,
        )
        db.add(ann)
        created.append(ann)

    if data:
        img.annotation_status = "in_progress"

    await db.commit()
    return {"created": len(created)}


@router.put("/{annotation_id}")
async def update_annotation(
    annotation_id: str,
    data: AnnotationUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(ann, field, value)

    await db.commit()
    await db.refresh(ann)
    return _serialize(ann)


@router.delete("/{annotation_id}", status_code=204)
async def delete_annotation(annotation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    await db.delete(ann)
    await db.commit()


@router.post("/images/{image_id}/mark-annotated")
async def mark_annotated(image_id: str, db: AsyncSession = Depends(get_db)):
    """Mark image as fully annotated (moves to review queue)."""
    result = await db.execute(select(Image).where(Image.id == image_id))
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    img.annotation_status = "annotated"
    await db.commit()
    return {"id": image_id, "annotation_status": "annotated"}
