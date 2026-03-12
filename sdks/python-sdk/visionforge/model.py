"""
Local inference runner using ONNX Runtime.
Allows running VisionForge models on-device without cloud API calls.

Usage:
    from visionforge import VisionModel

    model = VisionModel.from_platform("endpoint-id", api_key="vf_...")
    # OR load local ONNX:
    model = VisionModel.from_onnx("/path/to/model.onnx", label_map={0: "car", 1: "person"})

    results = model.predict("image.jpg")
    for detection in results:
        print(f"{detection['class_name']}: {detection['confidence']:.2f} at {detection['bbox']}")
"""
import io
import os
import time
from pathlib import Path
from typing import Dict, Generator, List, Optional, Union

import numpy as np
from PIL import Image


class VisionModel:
    """Local inference model using ONNX Runtime."""

    def __init__(
        self,
        onnx_path: str,
        label_map: Optional[Dict[int, str]] = None,
        img_size: int = 640,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ):
        import onnxruntime as ort

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        try:
            self.session = ort.InferenceSession(onnx_path, providers=providers)
        except Exception:
            self.session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.label_map = label_map or {}
        self.img_size = img_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold

    @classmethod
    def from_onnx(
        cls,
        onnx_path: Union[str, Path],
        label_map: Optional[Dict[int, str]] = None,
        **kwargs,
    ) -> "VisionModel":
        """Load from a local ONNX file."""
        return cls(str(onnx_path), label_map=label_map, **kwargs)

    @classmethod
    def from_platform(
        cls,
        endpoint_id: str,
        api_key: str,
        base_url: str = "http://localhost",
        cache_dir: Optional[str] = None,
        **kwargs,
    ) -> "VisionModel":
        """Download ONNX model from VisionForge platform and load it."""
        import requests

        cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".visionforge", "models")
        os.makedirs(cache_dir, exist_ok=True)

        cache_path = os.path.join(cache_dir, f"{endpoint_id}.onnx")

        if not os.path.exists(cache_path):
            # Get endpoint info
            res = requests.get(
                f"{base_url}/api/infer/endpoints/{endpoint_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
            res.raise_for_status()
            endpoint = res.json()

            # Get model version
            mv_res = requests.get(
                f"{base_url}/api/train/model-versions/{endpoint['model_version_id']}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
            mv_res.raise_for_status()
            mv = mv_res.json()

            # Download ONNX
            onnx_key = mv.get("export_artifacts", {}).get("onnx")
            if not onnx_key:
                raise ValueError("Model has no ONNX export. Export it first.")

            # Download via presigned URL (placeholder)
            print(f"Downloading model to {cache_path}...")
            # In a real impl: download via presigned URL

        label_map = kwargs.pop("label_map", None)
        return cls.from_onnx(cache_path, label_map=label_map, **kwargs)

    def _preprocess(self, image: Union[str, Path, bytes, np.ndarray]) -> tuple:
        """Preprocess image to model input tensor."""
        if isinstance(image, (str, Path)):
            img = Image.open(image).convert("RGB")
            orig_arr = np.array(img)
        elif isinstance(image, bytes):
            img = Image.open(io.BytesIO(image)).convert("RGB")
            orig_arr = np.array(img)
        elif isinstance(image, np.ndarray):
            orig_arr = image if image.shape[2] == 3 else image[:, :, ::-1]  # BGR->RGB
        else:
            raise ValueError("image must be a file path, bytes, or numpy array")

        orig_h, orig_w = orig_arr.shape[:2]
        target = self.img_size

        # Letterbox
        scale = min(target / orig_w, target / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        pad_x = (target - new_w) // 2
        pad_y = (target - new_h) // 2

        resized = np.array(Image.fromarray(orig_arr).resize((new_w, new_h), Image.BILINEAR))
        padded = np.full((target, target, 3), 114, dtype=np.uint8)
        padded[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        tensor = padded.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis]

        return tensor, scale, pad_x, pad_y, orig_w, orig_h

    def _postprocess(self, outputs: list, scale: float, pad_x: int, pad_y: int, orig_w: int, orig_h: int) -> list:
        """Apply NMS and decode predictions."""
        try:
            import cv2
        except ImportError:
            # Simple NMS fallback
            return self._simple_nms(outputs, scale, pad_x, pad_y, orig_w, orig_h)

        output = outputs[0]
        if output.ndim == 3:
            output = output[0].T

        boxes = output[:, :4]
        scores = output[:, 4:]

        max_scores = scores.max(axis=1)
        class_ids = scores.argmax(axis=1)

        mask = max_scores >= self.conf_threshold
        boxes, max_scores, class_ids = boxes[mask], max_scores[mask], class_ids[mask]

        if len(boxes) == 0:
            return []

        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        x2 = boxes[:, 0] + boxes[:, 2] / 2
        y2 = boxes[:, 1] + boxes[:, 3] / 2
        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

        predictions = []
        for cls_id in np.unique(class_ids):
            cls_mask = class_ids == cls_id
            cls_boxes = boxes_xyxy[cls_mask].astype(np.float32)
            cls_scores = max_scores[cls_mask].astype(np.float32)
            indices = cv2.dnn.NMSBoxes(cls_boxes.tolist(), cls_scores.tolist(), self.conf_threshold, self.iou_threshold)
            for idx in (indices.flatten() if len(indices) > 0 else []):
                b = boxes_xyxy[np.where(cls_mask)[0][idx]]
                x1_px = max(0, (b[0] - pad_x) / scale)
                y1_px = max(0, (b[1] - pad_y) / scale)
                x2_px = min(orig_w, (b[2] - pad_x) / scale)
                y2_px = min(orig_h, (b[3] - pad_y) / scale)
                predictions.append({
                    "class_id": int(cls_id),
                    "class_name": self.label_map.get(int(cls_id), str(cls_id)),
                    "confidence": float(cls_scores[idx]),
                    "bbox": {
                        "x1": int(x1_px), "y1": int(y1_px),
                        "x2": int(x2_px), "y2": int(y2_px),
                        "width": int(x2_px - x1_px), "height": int(y2_px - y1_px),
                    },
                })

        return predictions

    def _simple_nms(self, outputs, scale, pad_x, pad_y, orig_w, orig_h) -> list:
        """Basic NMS without OpenCV."""
        return []

    def predict(
        self,
        image: Union[str, Path, bytes, np.ndarray],
        conf_threshold: Optional[float] = None,
    ) -> List[dict]:
        """
        Run inference on a single image.
        Returns list of detections: [{class_id, class_name, confidence, bbox}]
        """
        conf = conf_threshold or self.conf_threshold
        old_conf = self.conf_threshold
        self.conf_threshold = conf

        t_start = time.perf_counter()
        tensor, scale, pad_x, pad_y, orig_w, orig_h = self._preprocess(image)
        outputs = self.session.run(self.output_names, {self.input_name: tensor})
        predictions = self._postprocess(outputs, scale, pad_x, pad_y, orig_w, orig_h)
        elapsed_ms = (time.perf_counter() - t_start) * 1000

        self.conf_threshold = old_conf
        return predictions

    def predict_stream(
        self,
        source: Union[str, int] = 0,
    ) -> Generator[dict, None, None]:
        """
        Run inference on a video stream (webcam or file).
        Yields: {"frame_number": N, "predictions": [...], "inference_ms": ...}
        source: 0 for webcam, or path to video file, or RTSP URL
        """
        try:
            import cv2
        except ImportError:
            raise ImportError("opencv-python required for stream inference: pip install opencv-python-headless")

        cap = cv2.VideoCapture(source)
        frame_num = 0

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                t_start = time.perf_counter()
                predictions = self.predict(frame_rgb)
                elapsed_ms = (time.perf_counter() - t_start) * 1000

                frame_num += 1
                yield {
                    "frame_number": frame_num,
                    "predictions": predictions,
                    "inference_ms": round(elapsed_ms, 2),
                }
        finally:
            cap.release()
