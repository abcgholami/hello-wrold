from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://visionforge:visionforge_secret@localhost:5432/visionforge"
    database_url_sync: str = "postgresql://visionforge:visionforge_secret@localhost:5432/visionforge"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO / S3
    minio_url: str = "http://localhost:9000"
    minio_access_key: str = "visionforge"
    minio_secret_key: str = "visionforge_secret"
    minio_bucket: str = "visionforge-media"

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_s3_endpoint_url: str = "http://localhost:9000"

    # AI Assist
    sam2_model: str = "sam2_hiera_large"
    clip_model: str = "openai/clip-vit-base-patch32"

    # Training temp dir
    training_temp_dir: str = "/tmp/visionforge"

    # CORS — comma-separated origins; defaults cover local dev stack
    allowed_origins: List[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:80",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
