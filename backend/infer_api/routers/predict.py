"""Single image and batch inference endpoints."""
import hashlib
import io
import time
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import InferenceEndpoint, ModelVersion, InferenceLog
from infer_api.engine_cache import ONNXInferenceEngine

router = APIRouter()


async def _get_engine(endpoint_id: str, request: Request, db: AsyncSession) -> tuple:
    """Load or retrieve from cache the inference engine for an endpoint."""
    result = await db.execute(
        select(InferenceEndpoint).where(InferenceEndpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Inference endpoint not found")
    if endpoint.status != "active":
        raise HTTPException(status_code=400, detail=f"Endpoint is not active (status: {endpoint.status})")

    # Load model version
    mv_result = await db.execute(
        select(ModelVersion).where(ModelVersion.id == endpoint.model_version_id)
    )
    mv = mv_result.scalar_one_or_none()
    if not mv:
        raise HTTPException(status_code=404, detail="Model version not found")

    cache = request.app.state.engine_cache
    engine = cache.get(mv.id)

    if engine is None:
        # Download ONNX model from MinIO
        onnx_key = None
        if mv.export_artifacts:
            onnx_key = mv.export_artifacts.get("onnx")

        if not onnx_key:
            raise HTTPException(status_code=400, detail="Model has no ONNX export. Please export to ONNX first.")

        from core_api.services.storage import download_file
        import tempfile, os
        model_data = download_file(onnx_key)
        tmp = tempfile.NamedTemporaryFile(suffix=".onnx", delete=False)
        tmp.write(model_data)
        tmp.close()

        engine = ONNXInferenceEngine(tmp.name, mv.id)
        cache.put(mv.id, engine)
        os.unlink(tmp.name)

    label_map = mv.export_artifacts.get("label_map", {}) if mv.export_artifacts else {}
    config = endpoint.config or {}
    return engine, label_map, config, endpoint, mv


@router.post("/{endpoint_id}")
async def predict_single(
    endpoint_id: str,
    request: Request,
    file: UploadFile = File(...),
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    db: AsyncSession = Depends(get_db),
):
    """Run inference on a single image."""
    engine, label_map, config, endpoint, mv = await _get_engine(endpoint_id, request, db)

    image_bytes = await file.read()

    # Preprocess
    target_size = (config.get("img_size", 640), config.get("img_size", 640))
    tensor, scale_x, scale_y, pad_x, pad_y, orig_w, orig_h = engine.preprocess(image_bytes, target_size)

    # Infer
    t_start = time.perf_counter()
    outputs = engine.infer(tensor)
    inference_ms = (time.perf_counter() - t_start) * 1000

    # Postprocess
    conf_thresh = config.get("confidence_threshold", confidence_threshold)
    iou_thresh = config.get("iou_threshold", iou_threshold)
    predictions = engine.postprocess(outputs, scale_x, scale_y, pad_x, pad_y, orig_w, orig_h, conf_thresh, iou_thresh, label_map)

    # Log (sampled at 5%)
    import random
    if random.random() < 0.05:
        img_hash = hashlib.md5(image_bytes).hexdigest()
        log = InferenceLog(
            endpoint_id=endpoint_id,
            image_hash=img_hash,
            predictions=predictions,
            confidence_scores=[p["confidence"] for p in predictions],
            inference_time_ms=int(inference_ms),
        )
        db.add(log)
        await db.commit()

    return {
        "predictions": predictions,
        "inference_time_ms": round(inference_ms, 2),
        "model_version_id": mv.id,
        "endpoint_id": endpoint_id,
    }


@router.post("/{endpoint_id}/base64")
async def predict_base64(
    endpoint_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Run inference on a base64-encoded image (JSON body)."""
    import base64
    body = await request.json()
    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(status_code=400, detail="Missing 'image' field in request body")

    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image")

    engine, label_map, config, endpoint, mv = await _get_engine(endpoint_id, request, db)

    target_size = (config.get("img_size", 640), config.get("img_size", 640))
    tensor, scale_x, scale_y, pad_x, pad_y, orig_w, orig_h = engine.preprocess(image_bytes, target_size)

    t_start = time.perf_counter()
    outputs = engine.infer(tensor)
    inference_ms = (time.perf_counter() - t_start) * 1000

    conf_thresh = config.get("confidence_threshold", body.get("confidence_threshold", 0.25))
    iou_thresh = config.get("iou_threshold", body.get("iou_threshold", 0.45))
    predictions = engine.postprocess(outputs, scale_x, scale_y, pad_x, pad_y, orig_w, orig_h, conf_thresh, iou_thresh, label_map)

    return {
        "predictions": predictions,
        "inference_time_ms": round(inference_ms, 2),
        "model_version_id": mv.id,
    }
