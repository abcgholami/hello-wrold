"""Vision processing nodes: DetectObjects, ClassifyImage, SegmentImage, TrackObjects, etc."""
from __future__ import annotations

import asyncio
from typing import Any, Optional

import numpy as np

from .base_node import BaseNode, NodeOutput


class DetectObjects(BaseNode):
    """Run object detection on a frame using an ONNX model."""

    node_type = "DetectObjects"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.model_path: str = config["model_path"]
        self.label_map: dict[int, str] = {int(k): v for k, v in config.get("label_map", {}).items()}
        self.conf_threshold: float = float(config.get("conf_threshold", 0.25))
        self.iou_threshold: float = float(config.get("iou_threshold", 0.45))
        self.class_filter: list[str] = config.get("class_filter", [])
        self._engine = None

    async def setup(self) -> None:
        from infer_api.engines.onnx_engine import engine_cache
        loop = asyncio.get_event_loop()
        self._engine = await loop.run_in_executor(None, engine_cache.get, self.model_path)

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        frame = upstream.get("frame")
        if frame is None:
            return None

        import cv2
        _, img_bytes = cv2.imencode(".jpg", frame)

        loop = asyncio.get_event_loop()
        predictions = await loop.run_in_executor(
            None,
            self._engine.predict,
            img_bytes.tobytes(),
            self.label_map,
            "detection",
            self.conf_threshold,
            self.iou_threshold,
        )

        if self.class_filter:
            predictions = [p for p in predictions if p.get("class") in self.class_filter]

        return NodeOutput({**upstream.data, "detections": predictions, "label_map": self.label_map})


class ClassifyImage(BaseNode):
    """Run image classification on a frame or cropped region."""

    node_type = "ClassifyImage"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.model_path: str = config["model_path"]
        self.label_map: dict[int, str] = {int(k): v for k, v in config.get("label_map", {}).items()}
        self.top_k: int = int(config.get("top_k", 3))
        self._engine = None

    async def setup(self) -> None:
        from infer_api.engines.onnx_engine import engine_cache
        loop = asyncio.get_event_loop()
        self._engine = await loop.run_in_executor(None, engine_cache.get, self.model_path)

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        frame = upstream.get("frame") or upstream.get("roi")
        if frame is None:
            return None

        import cv2
        _, img_bytes = cv2.imencode(".jpg", frame)

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            self._engine.predict,
            img_bytes.tobytes(),
            self.label_map,
            "classification",
            0.0,
            0.0,
        )

        top = results[: self.top_k] if results else []
        best = top[0] if top else {"class": "unknown", "confidence": 0.0}

        return NodeOutput({
            **upstream.data,
            "classification": top,
            "class": best.get("class"),
            "confidence": best.get("confidence"),
        })


class TrackObjects(BaseNode):
    """Wrap ByteTrack / SimpleIoUTracker around upstream detections."""

    node_type = "TrackObjects"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self._tracker = None

    async def setup(self) -> None:
        from infer_api.postprocessing.tracker import get_tracker
        self._tracker = get_tracker()

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        detections = upstream.get("detections", [])
        frame = upstream.get("frame")
        shape = frame.shape[:2] if frame is not None else (640, 640)

        tracks = self._tracker.update(detections, frame_shape=shape)
        return NodeOutput({**upstream.data, "tracks": [
            {
                "track_id": t.track_id,
                "class": t.class_name,
                "class_id": t.class_id,
                "confidence": t.confidence,
                "bbox": t.bbox,
                "age": t.age,
                "is_new": t.is_new,
            }
            for t in tracks
        ]})


class CountObjects(BaseNode):
    """Count unique track IDs crossing a configurable virtual line."""

    node_type = "CountObjects"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        # line: [[x1,y1],[x2,y2]]
        self.line: list[list[float]] = config.get("line", [[0, 0.5], [1, 0.5]])
        self.class_filter: list[str] = config.get("class_filter", [])
        self._crossed_ids: set[int] = set()
        self._prev_positions: dict[int, list[float]] = {}

    def _crossed_line(self, prev: list[float], curr: list[float]) -> bool:
        """Check if movement from prev→curr crosses the configured line (normalized coords)."""
        # Simple side-change test
        lx1, ly1 = self.line[0]
        lx2, ly2 = self.line[1]

        def side(px, py):
            return (lx2 - lx1) * (py - ly1) - (ly2 - ly1) * (px - lx1)

        s_prev = side(prev[0], prev[1])
        s_curr = side(curr[0], curr[1])
        return (s_prev * s_curr) < 0

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        tracks = upstream.get("tracks", [])

        new_crossings = []
        for track in tracks:
            tid = track["track_id"]
            bbox = track["bbox"]
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            curr_pos = [cx, cy]

            if self.class_filter and track.get("class") not in self.class_filter:
                self._prev_positions[tid] = curr_pos
                continue

            if tid in self._prev_positions and tid not in self._crossed_ids:
                if self._crossed_line(self._prev_positions[tid], curr_pos):
                    self._crossed_ids.add(tid)
                    new_crossings.append({"track_id": tid, "class": track.get("class"), "bbox": bbox})

            self._prev_positions[tid] = curr_pos

        count = len(self._crossed_ids)
        return NodeOutput({
            **upstream.data,
            "count": count,
            "new_crossings": new_crossings,
            "crossed_ids": list(self._crossed_ids),
        })


class ExtractROI(BaseNode):
    """Crop bounding box regions from the frame and output as roi."""

    node_type = "ExtractROI"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.class_filter: list[str] = config.get("class_filter", [])
        self.max_crops: int = int(config.get("max_crops", 5))

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        frame = upstream.get("frame")
        detections = upstream.get("detections", [])
        if frame is None:
            return None

        crops = []
        for det in detections[: self.max_crops]:
            if self.class_filter and det.get("class") not in self.class_filter:
                continue
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
            roi = frame[y1:y2, x1:x2]
            if roi.size > 0:
                crops.append({"roi": roi, "detection": det})

        if not crops:
            return None

        # Pass the first crop as the primary output (downstream nodes chain one-by-one)
        first = crops[0]
        return NodeOutput({**upstream.data, "roi": first["roi"], "roi_detection": first["detection"], "all_rois": crops})


class DrawAnnotations(BaseNode):
    """Render detections / tracks onto the frame using OpenCV."""

    node_type = "DrawAnnotations"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.show_tracks = bool(config.get("show_tracks", False))
        self.show_count = bool(config.get("show_count", True))

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        from infer_api.postprocessing.supervision_utils import draw_predictions_cv2, draw_tracks_cv2
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        frame = upstream.get("frame")
        if frame is None:
            return None

        annotated = frame.copy()

        if self.show_tracks and upstream.get("tracks"):
            # Build pseudo-Track objects for the drawing utility
            class _T:
                pass
            pseudo_tracks = []
            for t in upstream.get("tracks", []):
                obj = _T()
                obj.track_id = t["track_id"]
                obj.class_name = t.get("class", "")
                obj.class_id = t.get("class_id", 0)
                obj.confidence = t.get("confidence", 0.0)
                obj.bbox = t["bbox"]
                obj.is_lost = False
                obj.history = []
                pseudo_tracks.append(obj)
            annotated = draw_tracks_cv2(annotated, pseudo_tracks, show_trail=False)
        elif upstream.get("detections"):
            annotated = draw_predictions_cv2(annotated, upstream.get("detections", []))

        if self.show_count and upstream.get("count") is not None:
            import cv2
            cv2.putText(
                annotated,
                f"Count: {upstream['count']}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

        return NodeOutput({**upstream.data, "frame": annotated, "annotated_frame": annotated})
