"""Celery application factory with queue routing."""
from celery import Celery
from shared.config import get_settings

settings = get_settings()

celery_app = Celery(
    "visionforge",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "train_api.workers.training_tasks",
        "train_api.workers.export_tasks",
        "train_api.workers.dataset_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "train_model": {"queue": "gpu_training"},
        "export_model": {"queue": "default"},
        "export_dataset": {"queue": "export"},
        "execute_workflow": {"queue": "default"},
        "generate_thumbnails": {"queue": "default"},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # Important for GPU workers — process one job at a time
    task_track_started=True,
    result_expires=3600 * 24,  # Results kept 24 hours
)
