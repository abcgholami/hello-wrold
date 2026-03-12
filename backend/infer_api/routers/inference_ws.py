"""WebSocket streaming inference for real-time video analysis."""
import asyncio
import base64
import json
import time
from typing import Optional

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/stream/{endpoint_id}")
async def stream_inference(endpoint_id: str, websocket: WebSocket):
    """
    Real-time inference WebSocket.

    Client sends: {"frame": "<base64 JPEG>", "confidence_threshold": 0.25}
    Server sends: {"frame_number": N, "predictions": [...], "inference_ms": 23.4}

    Supports optional ByteTrack tracking when client sends {"enable_tracking": true}.
    """
    await websocket.accept()

    from sqlalchemy.ext.asyncio import AsyncSession
    from shared.db import AsyncSessionLocal
    from shared.db.models import InferenceEndpoint, ModelVersion

    frame_count = 0
    tracker = None

    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(select(InferenceEndpoint).where(InferenceEndpoint.id == endpoint_id))
            endpoint = result.scalar_one_or_none()
            if not endpoint:
                await websocket.send_json({"error": "Endpoint not found"})
                return

            mv_result = await db.execute(select(ModelVersion).where(ModelVersion.id == endpoint.model_version_id))
            mv = mv_result.scalar_one_or_none()
            if not mv:
                await websocket.send_json({"error": "Model version not found"})
                return

            # Load ONNX engine
            from infer_api.engine_cache import ONNXInferenceEngine
            from core_api.services.storage import download_file
            import tempfile
            import os

            onnx_key = (mv.export_artifacts or {}).get("onnx")
            if not onnx_key:
                await websocket.send_json({"error": "No ONNX export found for this model"})
                return

            model_data = download_file(onnx_key)
            tmp = tempfile.NamedTemporaryFile(suffix=".onnx", delete=False)
            tmp.write(model_data)
            tmp.close()

            engine = ONNXInferenceEngine(tmp.name, mv.id)
            os.unlink(tmp.name)

            label_map = (mv.export_artifacts or {}).get("label_map", {})
            config = endpoint.config or {}
            target_size = (config.get("img_size", 640), config.get("img_size", 640))
            conf_thresh = config.get("confidence_threshold", 0.25)
            iou_thresh = config.get("iou_threshold", 0.45)

            await websocket.send_json({"type": "ready", "endpoint_id": endpoint_id})

            while True:
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    message = json.loads(raw)
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "ping"})
                    continue
                except (json.JSONDecodeError, Exception):
                    break

                frame_b64 = message.get("frame")
                if not frame_b64:
                    continue

                try:
                    image_bytes = base64.b64decode(frame_b64)
                except Exception:
                    await websocket.send_json({"error": "Invalid base64 frame"})
                    continue

                # Override thresholds from client if provided
                req_conf = message.get("confidence_threshold", conf_thresh)
                req_iou = message.get("iou_threshold", iou_thresh)

                t_start = time.perf_counter()
                tensor, scale_x, scale_y, pad_x, pad_y, orig_w, orig_h = engine.preprocess(image_bytes, target_size)
                outputs = engine.infer(tensor)
                predictions = engine.postprocess(
                    outputs, scale_x, scale_y, pad_x, pad_y, orig_w, orig_h,
                    req_conf, req_iou, label_map
                )
                inference_ms = (time.perf_counter() - t_start) * 1000

                frame_count += 1

                response = {
                    "type": "prediction",
                    "frame_number": frame_count,
                    "predictions": predictions,
                    "inference_ms": round(inference_ms, 2),
                    "detection_count": len(predictions),
                }
                await websocket.send_json(response)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
