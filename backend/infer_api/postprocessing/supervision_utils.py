"""Utilities for rendering predictions onto frames using supervision (or fallback OpenCV)."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

try:
    import supervision as sv
    SV_AVAILABLE = True
except ImportError:
    SV_AVAILABLE = False


# Default colour palette (BGR)
_PALETTE = [
    (56, 56, 255), (151, 157, 255), (31, 112, 255), (29, 178, 255), (49, 210, 207),
    (10, 249, 72), (23, 204, 146), (134, 219, 61), (52, 147, 26), (187, 212, 0),
    (168, 153, 44), (255, 194, 0), (255, 108, 0), (226, 0, 0), (255, 0, 255),
]


def _color_for_class(class_id: int) -> tuple[int, int, int]:
    return _PALETTE[class_id % len(_PALETTE)]


def draw_predictions_cv2(
    frame: np.ndarray,
    predictions: list[dict],
    line_thickness: int = 2,
    font_scale: float = 0.6,
) -> np.ndarray:
    """Draw bounding boxes + labels on a BGR frame using OpenCV (no supervision required)."""
    out = frame.copy()
    for pred in predictions:
        bbox = pred.get("bbox")
        if bbox is None:
            continue
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        cls_id = pred.get("class_id", 0)
        color = _color_for_class(cls_id)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, line_thickness)
        label = f"{pred.get('class', '')} {pred.get('confidence', 0.0):.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        cv2.rectangle(out, (x1, y1 - th - 6), (x1 + tw + 2, y1), color, -1)
        cv2.putText(
            out,
            label,
            (x1 + 1, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return out


def draw_tracks_cv2(
    frame: np.ndarray,
    tracks: list,  # list of Track objects from tracker.py
    show_trail: bool = True,
    trail_length: int = 30,
) -> np.ndarray:
    """Draw track bounding boxes + IDs + centroid trails."""
    out = frame.copy()
    for track in tracks:
        if track.is_lost:
            continue
        x1, y1, x2, y2 = [int(v) for v in track.bbox]
        color = _color_for_class(track.class_id)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"ID:{track.track_id} {track.class_name} {track.confidence:.2f}"
        cv2.putText(out, label, (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        if show_trail and len(track.history) > 1:
            pts = track.history[-trail_length:]
            for i in range(1, len(pts)):
                alpha = int(255 * i / len(pts))
                t_color = tuple(int(c * alpha / 255) for c in color)
                cv2.line(out, (int(pts[i-1][0]), int(pts[i-1][1])), (int(pts[i][0]), int(pts[i][1])), t_color, 2)
    return out


def frame_to_jpeg(frame: np.ndarray, quality: int = 85) -> bytes:
    """Encode BGR frame to JPEG bytes."""
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()


def predictions_to_supervision(predictions: list[dict], frame_shape: tuple[int, int]) -> "sv.Detections":
    """Convert list of prediction dicts to supervision.Detections."""
    if not SV_AVAILABLE:
        raise RuntimeError("supervision is not installed: pip install supervision")
    if not predictions:
        return sv.Detections.empty()

    xyxy = np.array([p["bbox"] for p in predictions], dtype=np.float32)
    confs = np.array([p.get("confidence", 1.0) for p in predictions], dtype=np.float32)
    class_ids = np.array([p.get("class_id", 0) for p in predictions], dtype=int)
    return sv.Detections(xyxy=xyxy, confidence=confs, class_id=class_ids)
