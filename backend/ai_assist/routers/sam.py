"""
SAM2 (Segment Anything Model 2) segmentation endpoint.
Accepts point and bounding box prompts, returns binary mask + RLE encoding.
"""
import base64
import io
from typing import Any, List, Literal, Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_assist.sam_loader import get_sam_predictor

router = APIRouter()


class PointPrompt(BaseModel):
    type: Literal["point"] = "point"
    x: float  # Normalized [0,1]
    y: float  # Normalized [0,1]
    label: int = 1  # 1 = positive, 0 = negative


class BoxPrompt(BaseModel):
    type: Literal["bbox"] = "bbox"
    x: float      # top-left x normalized
    y: float      # top-left y normalized
    width: float  # normalized width
    height: float # normalized height


class SegmentRequest(BaseModel):
    image_id: str
    prompts: List[Any]  # List of PointPrompt or BoxPrompt dicts
    multimask_output: bool = False


class SegmentResponse(BaseModel):
    mask_b64: str         # Base64-encoded PNG mask (binary, 0/255)
    rle: Optional[dict]   # COCO RLE format: {counts: str, size: [H, W]}
    score: float
    width: int
    height: int


def _encode_rle(mask: np.ndarray) -> dict:
    """Encode binary mask as COCO RLE."""
    # Flatten mask column-major (Fortran order) as required by COCO
    flat = mask.flatten(order="F")
    rle_counts = []
    current = 0
    count = 0
    for val in flat:
        if val == current:
            count += 1
        else:
            rle_counts.append(count)
            count = 1
            current = val
    rle_counts.append(count)
    # COCO RLE starts with 0-count if the mask starts with 1
    if flat[0] == 1:
        rle_counts.insert(0, 0)
    return {"counts": rle_counts, "size": list(mask.shape)}


@router.post("/segment", response_model=SegmentResponse)
async def segment(req: SegmentRequest):
    """
    Run SAM2 segmentation on an image with given prompts.
    Returns the best mask as base64 PNG and COCO RLE.
    """
    # Load image from MinIO
    from core_api.services.storage import download_file
    from shared.db.models import Image
    from shared.db import AsyncSessionLocal
    from sqlalchemy import select
    from PIL import Image as PILImage

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Image).where(Image.id == req.image_id))
        image_record = result.scalar_one_or_none()
        if not image_record:
            raise HTTPException(status_code=404, detail="Image not found")

        image_bytes = download_file(image_record.storage_key)
        pil_img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(pil_img)
        img_h, img_w = img_array.shape[:2]

    # Get SAM predictor (lazy loaded)
    predictor = get_sam_predictor()
    if predictor is None:
        # Return empty mask if SAM2 not available (e.g., no GPU)
        empty_mask = np.zeros((img_h, img_w), dtype=np.uint8)
        buf = io.BytesIO()
        PILImage.fromarray(empty_mask).save(buf, format="PNG")
        return SegmentResponse(
            mask_b64=base64.b64encode(buf.getvalue()).decode(),
            rle={"counts": [img_h * img_w], "size": [img_h, img_w]},
            score=0.0,
            width=img_w,
            height=img_h,
        )

    predictor.set_image(img_array)

    # Parse prompts
    point_coords = []
    point_labels = []
    input_box = None

    for prompt in req.prompts:
        if isinstance(prompt, dict):
            if prompt.get("type") == "point":
                point_coords.append([prompt["x"] * img_w, prompt["y"] * img_h])
                point_labels.append(prompt.get("label", 1))
            elif prompt.get("type") == "bbox":
                x1 = prompt["x"] * img_w
                y1 = prompt["y"] * img_h
                x2 = x1 + prompt["width"] * img_w
                y2 = y1 + prompt["height"] * img_h
                input_box = np.array([x1, y1, x2, y2])

    point_coords_np = np.array(point_coords) if point_coords else None
    point_labels_np = np.array(point_labels) if point_labels else None

    masks, scores, _ = predictor.predict(
        point_coords=point_coords_np,
        point_labels=point_labels_np,
        box=input_box,
        multimask_output=req.multimask_output,
    )

    # Pick best mask (highest score)
    best_idx = int(np.argmax(scores))
    best_mask = masks[best_idx].astype(np.uint8) * 255
    best_score = float(scores[best_idx])

    # Encode as base64 PNG
    mask_img = PILImage.fromarray(best_mask, mode="L")
    buf = io.BytesIO()
    mask_img.save(buf, format="PNG")
    mask_b64 = base64.b64encode(buf.getvalue()).decode()

    # RLE encoding
    binary_mask = (best_mask > 127).astype(np.uint8)
    rle = _encode_rle(binary_mask)

    return SegmentResponse(
        mask_b64=mask_b64,
        rle=rle,
        score=best_score,
        width=img_w,
        height=img_h,
    )
