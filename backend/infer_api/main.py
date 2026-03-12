"""
VisionForge Inference API
Handles: real-time prediction, batch inference, video stream inference, API key auth.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from infer_api.routers import predict, inference_endpoints, inference_ws
from infer_api.engine_cache import ModelEngineCache

_cache: ModelEngineCache = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cache
    _cache = ModelEngineCache(max_size=5)
    app.state.engine_cache = _cache
    yield
    # Cleanup on shutdown
    _cache.clear()


app = FastAPI(
    title="VisionForge Inference API",
    version="1.0.0",
    description="High-performance inference with ONNX Runtime, batch processing, and video streams",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

app.include_router(predict.router, prefix="/predict", tags=["inference"])
app.include_router(inference_endpoints.router, prefix="/endpoints", tags=["endpoints"])
app.include_router(inference_ws.router, prefix="/ws", tags=["streaming"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "infer_api"}
