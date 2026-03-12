"""
VisionForge Training API
Handles: training job orchestration, model registry, real-time progress via WebSocket.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from shared.config import get_settings
from train_api.routers import training_jobs, model_versions, training_ws

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="VisionForge Training API",
    version="1.0.0",
    description="Training orchestration, model registry, and real-time progress streaming",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

app.include_router(training_jobs.router, prefix="/training-jobs", tags=["training"])
app.include_router(model_versions.router, prefix="/model-versions", tags=["models"])
app.include_router(training_ws.router, prefix="/ws", tags=["websocket"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "train_api"}
