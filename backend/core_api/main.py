"""
VisionForge Core API
Handles: auth, projects, datasets, images, annotations, label classes, exports, AI-assist proxy.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from shared.config import get_settings, warn_insecure_defaults
from core_api.routers import auth, projects, datasets, images, annotations, label_classes, exports, workflows
from core_api.services.storage import init_storage

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    warn_insecure_defaults()
    await init_storage()
    yield


app = FastAPI(
    title="VisionForge Core API",
    version="1.0.0",
    description="Core API for dataset management, annotation, and project orchestration",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

Instrumentator().instrument(app).expose(app)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
app.include_router(images.router, prefix="/images", tags=["images"])
app.include_router(annotations.router, prefix="/annotations", tags=["annotations"])
app.include_router(label_classes.router, prefix="/label-classes", tags=["label-classes"])
app.include_router(exports.router, prefix="/exports", tags=["exports"])
app.include_router(workflows.router, prefix="/workflows", tags=["workflows"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "core_api"}
