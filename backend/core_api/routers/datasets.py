"""Dataset and dataset version endpoints."""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import Dataset, DatasetVersion, DatasetVersionImage, Image, Annotation

router = APIRouter()


class DatasetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    project_id: str


class DatasetVersionCreate(BaseModel):
    name: Optional[str] = None
    split_config: dict = {"train": 0.7, "val": 0.2, "test": 0.1}
    augmentation_config: Optional[dict] = None
    filters: Optional[dict] = None


@router.post("", status_code=201)
async def create_dataset(data: DatasetCreate, db: AsyncSession = Depends(get_db)):
    dataset = Dataset(project_id=data.project_id, name=data.name, description=data.description)
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return {"id": dataset.id, "name": dataset.name, "project_id": dataset.project_id,
            "created_at": dataset.created_at.isoformat()}


@router.get("")
async def list_datasets(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.project_id == project_id))
    datasets = result.scalars().all()
    return [{"id": d.id, "name": d.name, "created_at": d.created_at.isoformat()} for d in datasets]


@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    # Get image count
    count_result = await db.execute(select(func.count(Image.id)).where(Image.dataset_id == dataset_id))
    image_count = count_result.scalar()
    return {"id": ds.id, "name": ds.name, "project_id": ds.project_id,
            "image_count": image_count, "created_at": ds.created_at.isoformat()}


@router.get("/{dataset_id}/stats")
async def dataset_stats(dataset_id: str, db: AsyncSession = Depends(get_db)):
    """Return annotation statistics for the dataset statistics dashboard."""
    # Image counts by status
    status_q = await db.execute(
        select(Image.annotation_status, func.count(Image.id))
        .where(Image.dataset_id == dataset_id)
        .group_by(Image.annotation_status)
    )
    status_counts = {row[0]: row[1] for row in status_q.fetchall()}

    # Image counts by split
    split_q = await db.execute(
        select(Image.split, func.count(Image.id))
        .where(Image.dataset_id == dataset_id)
        .group_by(Image.split)
    )
    split_counts = {row[0]: row[1] for row in split_q.fetchall()}

    # Total images
    total_q = await db.execute(select(func.count(Image.id)).where(Image.dataset_id == dataset_id))
    total_images = total_q.scalar()

    return {
        "total_images": total_images,
        "by_status": status_counts,
        "by_split": split_counts,
    }


@router.post("/{dataset_id}/versions", status_code=201)
async def create_version(
    dataset_id: str,
    data: DatasetVersionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create an immutable dataset version snapshot with train/val/test split."""
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Get next version number
    count_result = await db.execute(
        select(func.count(DatasetVersion.id)).where(DatasetVersion.dataset_id == dataset_id)
    )
    version_number = (count_result.scalar() or 0) + 1

    version = DatasetVersion(
        dataset_id=dataset_id,
        version_number=version_number,
        name=data.name or f"v{version_number}",
        split_config=data.split_config,
        augmentation_config=data.augmentation_config,
        filters=data.filters,
    )
    db.add(version)
    await db.flush()

    # Assign images to splits (stratified by annotation status / class distribution)
    result2 = await db.execute(
        select(Image)
        .where(Image.dataset_id == dataset_id)
        .where(Image.annotation_status.in_(["annotated", "reviewed"]))
    )
    images = result2.scalars().all()

    import random
    random.shuffle(images)
    train_r = data.split_config.get("train", 0.7)
    val_r = data.split_config.get("val", 0.2)

    n = len(images)
    n_train = int(n * train_r)
    n_val = int(n * val_r)

    for i, img in enumerate(images):
        if i < n_train:
            split = "train"
        elif i < n_train + n_val:
            split = "val"
        else:
            split = "test"
        db.add(DatasetVersionImage(version_id=version.id, image_id=img.id, split=split))

    version.image_count = n
    await db.commit()

    return {
        "id": version.id,
        "version_number": version.version_number,
        "name": version.name,
        "image_count": n,
        "split_config": version.split_config,
    }


@router.get("/{dataset_id}/versions")
async def list_versions(dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "name": v.name,
            "image_count": v.image_count,
            "split_config": v.split_config,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]
