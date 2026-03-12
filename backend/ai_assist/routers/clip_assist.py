"""CLIP-based classification suggestion endpoint."""
import io
from typing import List

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ClassifySuggestRequest(BaseModel):
    image_id: str
    class_names: List[str]
    top_k: int = 5


class ClassifySuggestResponse(BaseModel):
    suggestions: List[dict]  # [{class_name, confidence, rank}]


@router.post("/suggest", response_model=ClassifySuggestResponse)
async def suggest_classification(req: ClassifySuggestRequest):
    """
    Use CLIP to generate classification suggestions for an image.
    Returns top-k class matches with confidence scores.
    """
    if not req.class_names:
        raise HTTPException(status_code=400, detail="class_names cannot be empty")

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

    try:
        import torch
        from transformers import CLIPProcessor, CLIPModel
        from shared.config import get_settings
        settings = get_settings()

        # Lazy load CLIP model
        model_name = settings.clip_model
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        model.eval()

        inputs = processor(
            text=req.class_names,
            images=pil_img,
            return_tensors="pt",
            padding=True,
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1).cpu().numpy()[0]

        top_k = min(req.top_k, len(req.class_names))
        top_indices = np.argsort(probs)[::-1][:top_k]

        suggestions = [
            {
                "class_name": req.class_names[i],
                "confidence": float(probs[i]),
                "rank": rank + 1,
            }
            for rank, i in enumerate(top_indices)
        ]

    except ImportError:
        # Transformers not installed — return uniform distribution as fallback
        n = len(req.class_names)
        suggestions = [
            {"class_name": name, "confidence": 1.0 / n, "rank": i + 1}
            for i, name in enumerate(req.class_names[:req.top_k])
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CLIP inference failed: {str(e)}")

    return ClassifySuggestResponse(suggestions=suggestions)
