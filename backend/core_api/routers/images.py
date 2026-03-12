"""
Image upload, retrieval, and management endpoints.
Supports: single upload, batch ZIP, URL import, video frame extraction.
"""
import hashlib
import io
import os
import uuid
import zipfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import Dataset, Image, User
from shared.auth.deps import get_current_user, get_current_org_id
from core_api.services.storage import upload_file, get_presigned_url, delete_file
from core_api.services.thumbnail import extract_metadata, generate_thumbnails, compute_phash, phash_distance

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/bmp", "image/tiff", "image/webp"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


class ImageResponse(BaseModel):
    id: str
    filename: str
    width: int | None
    height: int | None
    split: str
    annotation_status: str
    thumb_url: str | None
    medium_url: str | None
    uploaded_at: str

    model_config = {"from_attributes": True}


async def _process_image(
    data: bytes,
    filename: str,
    dataset_id: str,
    org_id: str,
    project_id: str,
    db: AsyncSession,
    content_type: str = "image/jpeg",
) -> tuple[Image, bool]:
    """Store image, generate thumbnails, compute phash, create DB record.

    Returns (Image, is_duplicate) where is_duplicate is True when a
    near-identical image already exists in the dataset.
    """
    image_id = str(uuid.uuid4())
    safe_name = Path(filename).name  # strip any directory components
    ext = os.path.splitext(safe_name)[1].lower() or ".jpg"
    storage_key = f"orgs/{org_id}/projects/{project_id}/datasets/{dataset_id}/original/{image_id}{ext}"

    upload_file(data, storage_key, content_type)

    meta = extract_metadata(data)
    phash = compute_phash(data)

    # Near-duplicate check — bulk-fetch up to 500 hashes and compare in Python
    result = await db.execute(
        select(Image.phash).where(Image.dataset_id == dataset_id).limit(500)
    )
    existing_hashes = [r[0] for r in result.fetchall() if r[0]]
    is_duplicate = any(phash_distance(phash, eh) <= 8 for eh in existing_hashes)

    thumb_key, medium_key = generate_thumbnails(data, image_id, dataset_id, org_id, project_id)

    image = Image(
        id=image_id,
        dataset_id=dataset_id,
        filename=safe_name,
        storage_key=storage_key,
        thumb_key=thumb_key,
        medium_key=medium_key,
        width=meta["width"],
        height=meta["height"],
        file_size_bytes=len(data),
        phash=phash,
    )
    db.add(image)
    return image, is_duplicate


@router.post("/{dataset_id}/upload", status_code=201)
async def upload_images(
    dataset_id: str,
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    org_id: str | None = Depends(get_current_org_id),
):
    """Upload one or more image files to a dataset."""
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    resolved_org_id = org_id or "unknown"
    project_id = str(dataset.project_id)

    created = []
    duplicates = []
    skipped = []
    for file in files:
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            skipped.append(file.filename)
            continue
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"{file.filename} exceeds 50 MB limit")
        img, is_dup = await _process_image(
            data, file.filename or "image.jpg", dataset_id,
            resolved_org_id, project_id, db, file.content_type or "image/jpeg",
        )
        created.append(img)
        if is_dup:
            duplicates.append(img.id)

    await db.commit()
    return {
        "uploaded": len(created),
        "image_ids": [img.id for img in created],
        "duplicate_ids": duplicates,
        "skipped": skipped,
    }


@router.post("/{dataset_id}/upload-zip", status_code=202)
async def upload_zip(
    dataset_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    org_id: str | None = Depends(get_current_org_id),
):
    """Upload a ZIP archive of images — processed asynchronously."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Must be a ZIP file")

    data = await file.read()
    task_id = str(uuid.uuid4())
    resolved_org_id = org_id or "unknown"

    async def process_zip():
        from shared.db import AsyncSessionLocal
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            image_files = [n for n in zf.namelist() if not n.startswith("__MACOSX")]
            async with AsyncSessionLocal() as session:
                ds_result = await session.execute(select(Dataset).where(Dataset.id == dataset_id))
                ds = ds_result.scalar_one_or_none()
                if not ds:
                    return
                project_id = str(ds.project_id)
                for name in image_files:
                    ext = os.path.splitext(name)[1].lower()
                    if ext not in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"):
                        continue
                    img_data = zf.read(name)
                    if len(img_data) > MAX_UPLOAD_BYTES:
                        continue  # silently skip oversized files in batch
                    safe_name = Path(name).name
                    await _process_image(
                        img_data, safe_name, dataset_id,
                        resolved_org_id, project_id, session,
                    )
                await session.commit()

    background_tasks.add_task(process_zip)
    return {"task_id": task_id, "status": "processing"}


@router.get("/{dataset_id}/images")
async def list_images(
    dataset_id: str,
    split: str | None = None,
    annotation_status: str | None = None,
    page: int = 1,
    per_page: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List images in a dataset with optional filters."""
    query = select(Image).where(Image.dataset_id == dataset_id)
    if split:
        query = query.where(Image.split == split)
    if annotation_status:
        query = query.where(Image.annotation_status == annotation_status)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    query = query.offset((page - 1) * per_page).limit(per_page).order_by(Image.uploaded_at.desc())
    result = await db.execute(query)
    images = result.scalars().all()

    items = []
    for img in images:
        thumb_url = get_presigned_url(img.thumb_key) if img.thumb_key else None
        medium_url = get_presigned_url(img.medium_key) if img.medium_key else None
        items.append({
            "id": img.id,
            "filename": img.filename,
            "width": img.width,
            "height": img.height,
            "split": img.split,
            "annotation_status": img.annotation_status,
            "thumb_url": thumb_url,
            "medium_url": medium_url,
            "uploaded_at": img.uploaded_at.isoformat() if img.uploaded_at else None,
        })

    return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.get("/{image_id}")
async def get_image(
    image_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Image).where(Image.id == image_id))
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    return {
        "id": img.id,
        "filename": img.filename,
        "width": img.width,
        "height": img.height,
        "split": img.split,
        "annotation_status": img.annotation_status,
        "original_url": get_presigned_url(img.storage_key),
        "thumb_url": get_presigned_url(img.thumb_key) if img.thumb_key else None,
        "medium_url": get_presigned_url(img.medium_key) if img.medium_key else None,
        "phash": img.phash,
    }


@router.patch("/{image_id}/split")
async def update_split(
    image_id: str,
    split: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if split not in ("train", "val", "test", "unassigned"):
        raise HTTPException(status_code=400, detail="Invalid split value")
    result = await db.execute(select(Image).where(Image.id == image_id))
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    img.split = split
    await db.commit()
    return {"id": image_id, "split": split}


@router.delete("/{image_id}", status_code=204)
async def delete_image(
    image_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Image).where(Image.id == image_id))
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    delete_file(img.storage_key)
    if img.thumb_key:
        delete_file(img.thumb_key)
    if img.medium_key:
        delete_file(img.medium_key)

    await db.delete(img)
    await db.commit()
