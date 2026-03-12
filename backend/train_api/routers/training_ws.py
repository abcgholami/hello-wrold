"""WebSocket endpoint for real-time training progress streaming."""
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/training/{job_id}")
async def training_progress_ws(job_id: str, websocket: WebSocket):
    """
    Streams live training metrics to the browser.
    The Celery worker publishes epoch metrics to Redis Pub/Sub channel `training:{job_id}`.
    This endpoint subscribes and forwards to the WebSocket connection.
    """
    await websocket.accept()

    try:
        import redis.asyncio as aioredis
        from shared.config import get_settings
        settings = get_settings()

        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"training:{job_id}")

        await websocket.send_json({"type": "connected", "job_id": job_id})

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                    # If training is done, close gracefully
                    if data.get("status") in ("completed", "failed", "cancelled"):
                        break
                except json.JSONDecodeError:
                    continue

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await pubsub.unsubscribe(f"training:{job_id}")
            await redis.aclose()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
