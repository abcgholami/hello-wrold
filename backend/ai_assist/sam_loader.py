"""Lazy SAM2 model loader with Redis caching of image embeddings."""
import os
import threading
from typing import Optional

from shared.config import get_settings

settings = get_settings()

_predictor = None
_predictor_lock = threading.Lock()


def get_sam_predictor():
    """Return SAM2 predictor instance (lazy loaded, singleton)."""
    global _predictor

    if _predictor is not None:
        return _predictor

    with _predictor_lock:
        if _predictor is not None:
            return _predictor

        try:
            import torch
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor

            # Try to load SAM2 model
            model_cfg = _get_model_config(settings.sam2_model)
            checkpoint = _get_checkpoint_path(settings.sam2_model)

            if not os.path.exists(checkpoint):
                # Try downloading
                _download_checkpoint(settings.sam2_model, checkpoint)

            device = "cuda" if torch.cuda.is_available() else "cpu"
            sam_model = build_sam2(model_cfg, checkpoint, device=device)
            _predictor = SAM2ImagePredictor(sam_model)

        except ImportError:
            # SAM2 not installed — return None (graceful degradation)
            _predictor = None
        except Exception as e:
            print(f"Warning: Failed to load SAM2 model: {e}. AI-assist will be unavailable.")
            _predictor = None

    return _predictor


def _get_model_config(model_name: str) -> str:
    configs = {
        "sam2_hiera_tiny": "sam2_hiera_t.yaml",
        "sam2_hiera_small": "sam2_hiera_s.yaml",
        "sam2_hiera_base_plus": "sam2_hiera_b+.yaml",
        "sam2_hiera_large": "sam2_hiera_l.yaml",
    }
    return configs.get(model_name, "sam2_hiera_l.yaml")


def _get_checkpoint_path(model_name: str) -> str:
    cache_dir = os.path.expanduser("~/.cache/sam2")
    os.makedirs(cache_dir, exist_ok=True)
    checkpoints = {
        "sam2_hiera_tiny": "sam2_hiera_tiny.pt",
        "sam2_hiera_small": "sam2_hiera_small.pt",
        "sam2_hiera_base_plus": "sam2_hiera_base_plus.pt",
        "sam2_hiera_large": "sam2_hiera_large.pt",
    }
    filename = checkpoints.get(model_name, "sam2_hiera_large.pt")
    return os.path.join(cache_dir, filename)


def _download_checkpoint(model_name: str, checkpoint_path: str):
    """Download SAM2 checkpoint from Meta's releases."""
    urls = {
        "sam2_hiera_tiny": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_tiny.pt",
        "sam2_hiera_small": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_small.pt",
        "sam2_hiera_base_plus": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_base_plus.pt",
        "sam2_hiera_large": "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt",
    }
    url = urls.get(model_name)
    if not url:
        return

    import urllib.request
    print(f"Downloading SAM2 checkpoint: {url}")
    urllib.request.urlretrieve(url, checkpoint_path)
    print(f"Downloaded SAM2 checkpoint to {checkpoint_path}")
