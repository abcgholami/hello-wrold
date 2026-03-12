"""
VisionForge AI Assist Service
Handles: SAM2 segmentation, CLIP classification suggestions, auto-labeling.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_assist.routers import sam, clip_assist
from shared.config import get_settings, warn_insecure_defaults

settings = get_settings()
_sam_model = None
_clip_model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    warn_insecure_defaults()
    # Models are loaded lazily on first request to avoid startup delay
    yield


app = FastAPI(
    title="VisionForge AI Assist",
    version="1.0.0",
    description="SAM2 segmentation and CLIP-based classification suggestions",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(sam.router, prefix="/sam", tags=["sam2"])
app.include_router(clip_assist.router, prefix="/clip", tags=["clip"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai_assist"}
