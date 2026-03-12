"""ONNX Runtime inference engine with letterbox preprocessing and NMS postprocessing."""
from __future__ import annotations

import io
import threading
from pathlib import Path

import cv2
import numpy as np

try:
    import onnxruntime as ort
    ORT_AVAILABLE = True
except ImportError:
    ORT_AVAILABLE = False


def _letterbox(
    image: np.ndarray,
    target_size: tuple[int, int] = (640, 640),
    color: tuple[int, int, int] = (114, 114, 114),
) -> tuple[np.ndarray, float, float, int, int]:
    """Resize with padding to maintain aspect ratio.

    Returns (padded_image, scale_x, scale_y, pad_x, pad_y).
    """
    ih, iw = image.shape[:2]
    tw, th = target_size

    scale = min(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)

    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((th, tw, 3), color, dtype=np.uint8)
    pad_x = (tw - nw) // 2
    pad_y = (th - nh) // 2
    canvas[pad_y : pad_y + nh, pad_x : pad_x + nw] = resized

    scale_x = iw / nw
    scale_y = ih / nh
    return canvas, scale_x, scale_y, pad_x, pad_y


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Pure-numpy NMS (fallback when cv2 not available)."""
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-7)
        order = order[np.where(iou <= iou_threshold)[0] + 1]
    return keep


class ONNXEngine:
    """Wraps an ONNX model with preprocessing, postprocessing, and label mapping."""

    def __init__(self, model_path: str | Path, use_gpu: bool = False) -> None:
        if not ORT_AVAILABLE:
            raise RuntimeError("onnxruntime is not installed")

        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if use_gpu
            else ["CPUExecutionProvider"]
        )
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(model_path), sess_options=sess_options, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        input_shape = self.session.get_inputs()[0].shape  # [batch, C, H, W]
        self.input_h = input_shape[2] if isinstance(input_shape[2], int) else 640
        self.input_w = input_shape[3] if isinstance(input_shape[3], int) else 640

    # ------------------------------------------------------------------
    def preprocess(self, image_bytes: bytes) -> tuple[np.ndarray, tuple]:
        """Decode bytes → letterboxed float32 NCHW tensor.

        Returns (tensor, meta) where meta = (scale_x, scale_y, pad_x, pad_y, orig_w, orig_h).
        """
        arr = np.frombuffer(image_bytes, np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError("Failed to decode image bytes")
        orig_h, orig_w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        padded, sx, sy, px, py = _letterbox(rgb, (self.input_w, self.input_h))
        tensor = padded.astype(np.float32) / 255.0
        tensor = tensor.transpose(2, 0, 1)[np.newaxis]  # NCHW
        meta = (sx, sy, px, py, orig_w, orig_h)
        return tensor, meta

    # ------------------------------------------------------------------
    def run(self, tensor: np.ndarray) -> list[np.ndarray]:
        return self.session.run(None, {self.input_name: tensor})

    # ------------------------------------------------------------------
    def postprocess_detection(
        self,
        outputs: list[np.ndarray],
        meta: tuple,
        label_map: dict[int, str],
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ) -> list[dict]:
        """Parse YOLOv8 detection output [1, num_classes+4, num_anchors].

        Returns list of {"class", "confidence", "bbox": [x1,y1,x2,y2]}.
        """
        sx, sy, px, py, orig_w, orig_h = meta
        raw = outputs[0]  # shape: [1, 4+nc, 8400]
        if raw.ndim == 3:
            raw = raw[0]  # [4+nc, 8400]
        raw = raw.T  # [8400, 4+nc]

        boxes_xywh = raw[:, :4]
        class_scores = raw[:, 4:]

        best_cls = class_scores.argmax(axis=1)
        best_conf = class_scores.max(axis=1)
        mask = best_conf >= conf_threshold

        boxes_xywh = boxes_xywh[mask]
        best_cls = best_cls[mask]
        best_conf = best_conf[mask]

        if len(boxes_xywh) == 0:
            return []

        # cx,cy,w,h in input-space → xyxy in original-image space
        cx, cy, w, h = boxes_xywh.T
        x1 = (cx - w / 2 - px) * sx
        y1 = (cy - h / 2 - py) * sy
        x2 = (cx + w / 2 - px) * sx
        y2 = (cy + h / 2 - py) * sy
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)
        xyxy = np.stack([x1, y1, x2, y2], axis=1)

        results = []
        for cls_id in np.unique(best_cls):
            cls_mask = best_cls == cls_id
            cls_boxes = xyxy[cls_mask]
            cls_scores_arr = best_conf[cls_mask]
            keep = _nms(cls_boxes, cls_scores_arr, iou_threshold)
            for i in keep:
                b = cls_boxes[i]
                results.append(
                    {
                        "class": label_map.get(int(cls_id), str(cls_id)),
                        "class_id": int(cls_id),
                        "confidence": float(cls_scores_arr[i]),
                        "bbox": [float(b[0]), float(b[1]), float(b[2]), float(b[3])],
                    }
                )
        return results

    # ------------------------------------------------------------------
    def postprocess_classification(
        self,
        outputs: list[np.ndarray],
        label_map: dict[int, str],
        top_k: int = 5,
    ) -> list[dict]:
        """Parse softmax classification output."""
        logits = outputs[0][0]
        probs = np.exp(logits - logits.max()) / np.exp(logits - logits.max()).sum()
        top_indices = probs.argsort()[::-1][:top_k]
        return [
            {"class": label_map.get(int(i), str(i)), "class_id": int(i), "confidence": float(probs[i])}
            for i in top_indices
        ]

    # ------------------------------------------------------------------
    def predict(
        self,
        image_bytes: bytes,
        label_map: dict[int, str],
        task_type: str = "detection",
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ) -> list[dict]:
        """End-to-end predict: bytes → structured predictions."""
        tensor, meta = self.preprocess(image_bytes)
        outputs = self.run(tensor)
        if task_type == "classification":
            return self.postprocess_classification(outputs, label_map)
        return self.postprocess_detection(outputs, meta, label_map, conf_threshold, iou_threshold)


class ModelEngineCache:
    """Thread-safe LRU cache for ONNXEngine instances (max 5 models in memory)."""

    def __init__(self, max_size: int = 5) -> None:
        self._cache: dict[str, ONNXEngine] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._max_size = max_size

    def get(self, model_path: str, use_gpu: bool = False) -> ONNXEngine:
        with self._lock:
            if model_path in self._cache:
                self._order.remove(model_path)
                self._order.append(model_path)
                return self._cache[model_path]
            if len(self._cache) >= self._max_size:
                evict_key = self._order.pop(0)
                del self._cache[evict_key]
            engine = ONNXEngine(model_path, use_gpu=use_gpu)
            self._cache[model_path] = engine
            self._order.append(model_path)
            return engine

    def invalidate(self, model_path: str) -> None:
        with self._lock:
            if model_path in self._cache:
                del self._cache[model_path]
                self._order.remove(model_path)


# Module-level singleton
engine_cache = ModelEngineCache(max_size=5)
