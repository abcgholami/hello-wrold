"""MinIO S3-compatible object storage service."""
import io
from typing import Optional

from minio import Minio
from minio.error import S3Error

from shared.config import get_settings

settings = get_settings()

_client: Optional[Minio] = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_url.replace("http://", "").replace("https://", ""),
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_url.startswith("https"),
        )
    return _client


async def init_storage():
    """Ensure required buckets exist."""
    client = get_client()
    buckets = [settings.minio_bucket, "visionforge-mlflow", "visionforge-exports"]
    for bucket in buckets:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)


def upload_file(
    data: bytes,
    storage_key: str,
    content_type: str = "application/octet-stream",
    bucket: Optional[str] = None,
) -> str:
    """Upload bytes to MinIO. Returns the storage key."""
    client = get_client()
    bucket = bucket or settings.minio_bucket
    client.put_object(
        bucket_name=bucket,
        object_name=storage_key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return storage_key


def download_file(storage_key: str, bucket: Optional[str] = None) -> bytes:
    client = get_client()
    bucket = bucket or settings.minio_bucket
    response = client.get_object(bucket_name=bucket, object_name=storage_key)
    data = response.read()
    response.close()
    return data


def get_presigned_url(storage_key: str, expires_seconds: int = 3600, bucket: Optional[str] = None) -> str:
    """Return a presigned GET URL for direct browser access."""
    from datetime import timedelta
    client = get_client()
    bucket = bucket or settings.minio_bucket
    return client.presigned_get_object(
        bucket_name=bucket,
        object_name=storage_key,
        expires=timedelta(seconds=expires_seconds),
    )


def delete_file(storage_key: str, bucket: Optional[str] = None):
    client = get_client()
    bucket = bucket or settings.minio_bucket
    try:
        client.remove_object(bucket_name=bucket, object_name=storage_key)
    except S3Error:
        pass
