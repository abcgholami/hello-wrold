"""PyTorch inference engine for development use (before ONNX export)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False


class PyTorchEngine:
    """Thin wrapper around Ultralytics YOLO for PyTorch inference.

    Used when the model has not been exported to ONNX yet, or for rapid
    iteration during development. Not recommended for high-throughput
    production use — prefer ONNXEngine or Triton.
    """

    def __init__(self, model_path: str | Path) -> None:
        if not ULTRALYTICS_AVAILABLE:
            raise RuntimeError("ultralytics is not installed; cannot use PyTorchEngine")
        self.model = YOLO(str(model_path))
        self.device = "cuda" if (TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"
        self.model.to(self.device)

    # ------------------------------------------------------------------
    def predict(
        self,
        image_bytes: bytes,
        label_map: dict[int, str],
        task_type: str = "detection",
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ) -> list[dict]:
        import io
        from PIL import Image as PILImage

        img = PILImage.open(io.BytesIO(image_bytes))
        results = self.model(img, conf=conf_threshold, iou=iou_threshold, verbose=False)[0]

        predictions: list[dict] = []

        if task_type == "classification":
            probs = results.probs
            if probs is not None:
                top5 = probs.top5
                top5conf = probs.top5conf.cpu().numpy()
                for rank, (cls_id, conf) in enumerate(zip(top5, top5conf)):
                    predictions.append(
                        {
                            "class": label_map.get(int(cls_id), str(cls_id)),
                            "class_id": int(cls_id),
                            "confidence": float(conf),
                        }
                    )
        else:
            boxes = results.boxes
            if boxes is not None:
                xyxy = boxes.xyxy.cpu().numpy()
                confs = boxes.conf.cpu().numpy()
                clss = boxes.cls.cpu().numpy().astype(int)
                for i in range(len(xyxy)):
                    predictions.append(
                        {
                            "class": label_map.get(int(clss[i]), str(clss[i])),
                            "class_id": int(clss[i]),
                            "confidence": float(confs[i]),
                            "bbox": xyxy[i].tolist(),
                        }
                    )
        return predictions
