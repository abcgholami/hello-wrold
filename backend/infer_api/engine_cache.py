"""LRU cache for loaded inference engines to avoid repeated model loads."""
import threading
from collections import OrderedDict
from typing import Optional

import onnxruntime as ort
import numpy as np


class ONNXInferenceEngine:
    """Wraps ONNX Runtime session with pre/post processing."""

    def __init__(self, model_path: str, model_version_id: str):
        self.model_version_id = model_version_id
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        try:
            self.session = ort.InferenceSession(model_path, providers=providers)
        except Exception:
            self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])

        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.output_names = [o.name for o in self.session.get_outputs()]

    def infer(self, image_tensor: np.ndarray) -> list:
        """Run inference. image_tensor: [1, 3, H, W] float32 normalized."""
        outputs = self.session.run(self.output_names, {self.input_name: image_tensor})
        return outputs

    def preprocess(self, image_bytes: bytes, target_size: tuple = (640, 640)) -> tuple:
        """Preprocess image bytes to model input tensor. Returns (tensor, scale_x, scale_y, pad_x, pad_y)."""
        import cv2
        import io
        from PIL import Image

        # Decode image
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            img_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img = np.array(img_pil)[:, :, ::-1]  # RGB to BGR

        orig_h, orig_w = img.shape[:2]
        target_h, target_w = target_size

        # Letterbox resize
        scale = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2
        padded = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        padded[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        # Normalize and convert to tensor
        tensor = padded.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))  # HWC to CHW
        tensor = np.expand_dims(tensor, 0)  # Add batch dim

        return tensor, scale, scale, pad_x, pad_y, orig_w, orig_h

    def postprocess(
        self,
        outputs: list,
        scale_x: float,
        scale_y: float,
        pad_x: int,
        pad_y: int,
        orig_w: int,
        orig_h: int,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        label_map: dict = None,
    ) -> list:
        """Apply NMS and convert to normalized prediction format."""
        import cv2

        predictions = []
        if not outputs:
            return predictions

        # YOLOv8 output format: [1, num_classes+4, num_anchors]
        output = outputs[0]
        if output.ndim == 3:
            output = output[0].T  # [num_anchors, num_classes+4]

        boxes = output[:, :4]  # cx, cy, w, h
        scores = output[:, 4:]

        max_scores = scores.max(axis=1)
        class_ids = scores.argmax(axis=1)

        mask = max_scores >= conf_threshold
        boxes = boxes[mask]
        max_scores = max_scores[mask]
        class_ids = class_ids[mask]

        if len(boxes) == 0:
            return predictions

        # Convert cx,cy,w,h to x1,y1,x2,y2
        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        x2 = boxes[:, 0] + boxes[:, 2] / 2
        y2 = boxes[:, 1] + boxes[:, 3] / 2

        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

        # Apply NMS per class
        keep_indices = []
        for cls_id in np.unique(class_ids):
            cls_mask = class_ids == cls_id
            cls_boxes = boxes_xyxy[cls_mask].astype(np.float32)
            cls_scores = max_scores[cls_mask].astype(np.float32)
            indices = cv2.dnn.NMSBoxes(
                cls_boxes.tolist(), cls_scores.tolist(), conf_threshold, iou_threshold
            )
            if len(indices) > 0:
                keep_indices.extend(np.where(cls_mask)[0][indices.flatten()].tolist())

        for idx in keep_indices:
            x1_px = (boxes_xyxy[idx, 0] - pad_x) / scale_x
            y1_px = (boxes_xyxy[idx, 1] - pad_y) / scale_y
            x2_px = (boxes_xyxy[idx, 2] - pad_x) / scale_x
            y2_px = (boxes_xyxy[idx, 3] - pad_y) / scale_y

            # Clamp to image bounds
            x1_norm = max(0.0, min(1.0, x1_px / orig_w))
            y1_norm = max(0.0, min(1.0, y1_px / orig_h))
            x2_norm = max(0.0, min(1.0, x2_px / orig_w))
            y2_norm = max(0.0, min(1.0, y2_px / orig_h))

            cls_id = int(class_ids[idx])
            class_name = (label_map or {}).get(str(cls_id), str(cls_id))

            predictions.append({
                "class_id": cls_id,
                "class_name": class_name,
                "confidence": float(max_scores[idx]),
                "bbox": {
                    "x": x1_norm,
                    "y": y1_norm,
                    "width": x2_norm - x1_norm,
                    "height": y2_norm - y1_norm,
                },
            })

        return predictions


class ModelEngineCache:
    """Thread-safe LRU cache for inference engines."""

    def __init__(self, max_size: int = 5):
        self.max_size = max_size
        self._cache: OrderedDict[str, ONNXInferenceEngine] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, model_version_id: str) -> Optional[ONNXInferenceEngine]:
        with self._lock:
            if model_version_id in self._cache:
                self._cache.move_to_end(model_version_id)
                return self._cache[model_version_id]
        return None

    def put(self, model_version_id: str, engine: ONNXInferenceEngine):
        with self._lock:
            if model_version_id in self._cache:
                self._cache.move_to_end(model_version_id)
            else:
                if len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)
                self._cache[model_version_id] = engine

    def clear(self):
        with self._lock:
            self._cache.clear()
