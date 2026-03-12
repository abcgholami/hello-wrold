"""
Albumentations pipeline builder service.
Serializes/deserializes augmentation configs and applies them to images+annotations.
"""
from typing import Any

import albumentations as A
import cv2
import numpy as np


# Catalog of available transforms for the UI
TRANSFORM_CATALOG = {
    "geometric": [
        {"type": "HorizontalFlip", "params": {"p": {"type": "float", "default": 0.5, "min": 0, "max": 1}}},
        {"type": "VerticalFlip", "params": {"p": {"type": "float", "default": 0.5, "min": 0, "max": 1}}},
        {"type": "RandomRotate90", "params": {"p": {"type": "float", "default": 0.5, "min": 0, "max": 1}}},
        {"type": "Rotate", "params": {
            "limit": {"type": "int", "default": 45, "min": 1, "max": 180},
            "p": {"type": "float", "default": 0.5, "min": 0, "max": 1},
        }},
        {"type": "ShiftScaleRotate", "params": {
            "shift_limit": {"type": "float", "default": 0.1, "min": 0, "max": 0.5},
            "scale_limit": {"type": "float", "default": 0.1, "min": 0, "max": 0.5},
            "rotate_limit": {"type": "int", "default": 45, "min": 0, "max": 180},
            "p": {"type": "float", "default": 0.5, "min": 0, "max": 1},
        }},
        {"type": "RandomCrop", "params": {
            "height": {"type": "int", "default": 512, "min": 64, "max": 4096},
            "width": {"type": "int", "default": 512, "min": 64, "max": 4096},
            "p": {"type": "float", "default": 1.0, "min": 0, "max": 1},
        }},
        {"type": "Perspective", "params": {
            "scale": {"type": "float", "default": 0.05, "min": 0, "max": 0.3},
            "p": {"type": "float", "default": 0.5, "min": 0, "max": 1},
        }},
    ],
    "color": [
        {"type": "RandomBrightnessContrast", "params": {
            "brightness_limit": {"type": "float", "default": 0.2, "min": 0, "max": 0.5},
            "contrast_limit": {"type": "float", "default": 0.2, "min": 0, "max": 0.5},
            "p": {"type": "float", "default": 0.5, "min": 0, "max": 1},
        }},
        {"type": "HueSaturationValue", "params": {
            "hue_shift_limit": {"type": "int", "default": 20, "min": 0, "max": 180},
            "sat_shift_limit": {"type": "int", "default": 30, "min": 0, "max": 255},
            "val_shift_limit": {"type": "int", "default": 20, "min": 0, "max": 255},
            "p": {"type": "float", "default": 0.5, "min": 0, "max": 1},
        }},
        {"type": "ColorJitter", "params": {
            "brightness": {"type": "float", "default": 0.2, "min": 0, "max": 1},
            "contrast": {"type": "float", "default": 0.2, "min": 0, "max": 1},
            "saturation": {"type": "float", "default": 0.2, "min": 0, "max": 1},
            "hue": {"type": "float", "default": 0.1, "min": 0, "max": 0.5},
            "p": {"type": "float", "default": 0.5, "min": 0, "max": 1},
        }},
        {"type": "ToGray", "params": {"p": {"type": "float", "default": 0.1, "min": 0, "max": 1}}},
        {"type": "CLAHE", "params": {
            "clip_limit": {"type": "float", "default": 4.0, "min": 1, "max": 40},
            "p": {"type": "float", "default": 0.5, "min": 0, "max": 1},
        }},
    ],
    "blur": [
        {"type": "Blur", "params": {
            "blur_limit": {"type": "int", "default": 7, "min": 3, "max": 21},
            "p": {"type": "float", "default": 0.3, "min": 0, "max": 1},
        }},
        {"type": "GaussianBlur", "params": {
            "blur_limit": {"type": "int", "default": 7, "min": 3, "max": 21},
            "p": {"type": "float", "default": 0.3, "min": 0, "max": 1},
        }},
        {"type": "MotionBlur", "params": {
            "blur_limit": {"type": "int", "default": 7, "min": 3, "max": 21},
            "p": {"type": "float", "default": 0.2, "min": 0, "max": 1},
        }},
    ],
    "noise": [
        {"type": "GaussNoise", "params": {
            "var_limit": {"type": "float", "default": 10.0, "min": 0, "max": 100},
            "p": {"type": "float", "default": 0.3, "min": 0, "max": 1},
        }},
        {"type": "ISONoise", "params": {
            "color_shift": {"type": "float", "default": 0.05, "min": 0, "max": 0.5},
            "intensity": {"type": "float", "default": 0.5, "min": 0, "max": 1},
            "p": {"type": "float", "default": 0.3, "min": 0, "max": 1},
        }},
        {"type": "ImageCompression", "params": {
            "quality_lower": {"type": "int", "default": 60, "min": 1, "max": 100},
            "p": {"type": "float", "default": 0.2, "min": 0, "max": 1},
        }},
    ],
    "weather": [
        {"type": "RandomFog", "params": {"p": {"type": "float", "default": 0.2, "min": 0, "max": 1}}},
        {"type": "RandomRain", "params": {"p": {"type": "float", "default": 0.2, "min": 0, "max": 1}}},
        {"type": "RandomShadow", "params": {"p": {"type": "float", "default": 0.2, "min": 0, "max": 1}}},
        {"type": "RandomSunFlare", "params": {"p": {"type": "float", "default": 0.1, "min": 0, "max": 1}}},
    ],
}


def build_pipeline(config: dict) -> A.Compose:
    """
    Build an Albumentations Compose pipeline from JSON config.
    Config format: {"transforms": [{"type": "HorizontalFlip", "p": 0.5}, ...]}
    """
    return A.from_dict(config)


def apply_pipeline(
    pipeline: A.Compose,
    image: np.ndarray,
    bboxes: list | None = None,
    masks: list | None = None,
) -> dict:
    """
    Apply augmentation pipeline. Returns dict with image, bboxes, masks.
    bboxes: list of [x_min, y_min, x_max, y_max, class_label] (Pascal VOC format, unnormalized)
    """
    kwargs: dict[str, Any] = {"image": image}
    if bboxes is not None:
        kwargs["bboxes"] = [b[:4] for b in bboxes]
        kwargs["category_ids"] = [b[4] for b in bboxes]
    if masks is not None:
        kwargs["masks"] = masks
    return pipeline(**kwargs)


def get_catalog() -> dict:
    return TRANSFORM_CATALOG
