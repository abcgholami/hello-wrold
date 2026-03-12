"""Image thumbnail and metadata extraction service."""
import io
from typing import Tuple

from PIL import Image, ExifTags

from core_api.services.storage import upload_file

THUMB_SIZE = (256, 256)
MEDIUM_SIZE = (800, 800)


def extract_metadata(data: bytes) -> dict:
    with Image.open(io.BytesIO(data)) as img:
        width, height = img.size
        fmt = img.format or "JPEG"
    return {"width": width, "height": height, "format": fmt}


def generate_thumbnails(
    image_data: bytes,
    image_id: str,
    dataset_id: str,
    project_id: str,
) -> Tuple[str, str]:
    """Generate 256px thumbnail and 800px medium image. Returns (thumb_key, medium_key)."""
    base = f"projects/{project_id}/datasets/{dataset_id}/thumbs/{image_id}"

    with Image.open(io.BytesIO(image_data)) as img:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        thumb = img.copy()
        thumb.thumbnail(THUMB_SIZE, Image.LANCZOS)
        thumb_buf = io.BytesIO()
        thumb.save(thumb_buf, format="JPEG", quality=85)
        thumb_key = base + "_thumb.jpg"
        upload_file(thumb_buf.getvalue(), thumb_key, "image/jpeg")

        medium = img.copy()
        medium.thumbnail(MEDIUM_SIZE, Image.LANCZOS)
        medium_buf = io.BytesIO()
        medium.save(medium_buf, format="JPEG", quality=88)
        medium_key = base + "_medium.jpg"
        upload_file(medium_buf.getvalue(), medium_key, "image/jpeg")

    return thumb_key, medium_key


def compute_phash(image_data: bytes) -> str:
    import imagehash
    with Image.open(io.BytesIO(image_data)) as img:
        return str(imagehash.phash(img))


def phash_distance(hash1: str, hash2: str) -> int:
    import imagehash
    return imagehash.hex_to_hash(hash1) - imagehash.hex_to_hash(hash2)
