"""Non-Maximum Suppression utilities."""
from __future__ import annotations

import numpy as np


def nms_numpy(
    boxes: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float = 0.45,
) -> list[int]:
    """Pure NumPy NMS returning indices of kept boxes.

    Args:
        boxes: [N, 4] array in xyxy format.
        scores: [N] confidence scores.
        iou_threshold: Boxes with IoU > this with a higher-scored box are suppressed.
    """
    if len(boxes) == 0:
        return []

    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []

    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        rest = order[1:]
        ix1 = np.maximum(x1[i], x1[rest])
        iy1 = np.maximum(y1[i], y1[rest])
        ix2 = np.minimum(x2[i], x2[rest])
        iy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0.0, ix2 - ix1) * np.maximum(0.0, iy2 - iy1)
        iou = inter / (areas[i] + areas[rest] - inter + 1e-7)
        order = rest[iou <= iou_threshold]

    return keep


def batched_nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    class_ids: np.ndarray,
    iou_threshold: float = 0.45,
) -> list[int]:
    """Per-class NMS: offset boxes by class id to isolate classes, then run NMS."""
    if len(boxes) == 0:
        return []
    max_coord = boxes.max() + 1
    offsets = class_ids.astype(np.float32) * max_coord
    shifted_boxes = boxes + offsets[:, np.newaxis]
    return nms_numpy(shifted_boxes, scores, iou_threshold)
