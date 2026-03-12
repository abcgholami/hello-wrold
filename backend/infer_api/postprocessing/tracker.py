"""ByteTrack-based multi-object tracker wrapper.

Falls back to a simple IoU tracker when boxmot/ByteTrack is not installed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

try:
    from boxmot import ByteTracker
    BOXMOT_AVAILABLE = True
except ImportError:
    BOXMOT_AVAILABLE = False


@dataclass
class Track:
    track_id: int
    class_name: str
    class_id: int
    confidence: float
    bbox: list[float]          # [x1, y1, x2, y2]
    age: int = 1               # frames since first seen
    is_new: bool = True
    is_lost: bool = False
    history: list[list[float]] = field(default_factory=list)


class ByteTrackWrapper:
    """Thin wrapper around boxmot.ByteTracker for use in the infer_api."""

    def __init__(
        self,
        track_thresh: float = 0.25,
        track_buffer: int = 30,
        match_thresh: float = 0.8,
        frame_rate: int = 30,
    ) -> None:
        if not BOXMOT_AVAILABLE:
            raise RuntimeError(
                "boxmot is not installed. Install with: pip install boxmot"
            )
        self.tracker = ByteTracker(
            track_thresh=track_thresh,
            track_buffer=track_buffer,
            match_thresh=match_thresh,
            frame_rate=frame_rate,
        )
        self._tracks: dict[int, Track] = {}
        self._frame_idx = 0

    def update(
        self,
        detections: list[dict],
        frame_shape: tuple[int, int] = (640, 640),
    ) -> list[Track]:
        """Update tracker with new detections.

        Args:
            detections: List of {"bbox": [x1,y1,x2,y2], "confidence": float,
                                  "class_id": int, "class": str}
            frame_shape: (height, width) of the source frame.

        Returns:
            List of active Track objects.
        """
        self._frame_idx += 1
        if not detections:
            self.tracker.update(np.empty((0, 6)), frame_shape)
            # Mark existing tracks as lost
            for t in self._tracks.values():
                t.is_lost = True
                t.is_new = False
            return [t for t in self._tracks.values() if not t.is_lost]

        # Build [x1, y1, x2, y2, conf, cls] array
        det_array = np.array(
            [
                d["bbox"] + [d["confidence"], d.get("class_id", 0)]
                for d in detections
            ],
            dtype=np.float32,
        )

        tracked = self.tracker.update(det_array, frame_shape)
        # tracked: [x1, y1, x2, y2, track_id, conf, cls, ...]

        active_ids: set[int] = set()
        active_tracks: list[Track] = []

        for row in tracked:
            x1, y1, x2, y2 = row[0], row[1], row[2], row[3]
            tid = int(row[4])
            conf = float(row[5])
            cls_id = int(row[6])
            cls_name = next(
                (d["class"] for d in detections if d.get("class_id") == cls_id),
                str(cls_id),
            )
            bbox = [float(x1), float(y1), float(x2), float(y2)]
            active_ids.add(tid)

            if tid in self._tracks:
                t = self._tracks[tid]
                t.bbox = bbox
                t.confidence = conf
                t.age += 1
                t.is_new = False
                t.is_lost = False
                t.history.append([(x1 + x2) / 2, (y1 + y2) / 2])  # centroid
            else:
                t = Track(
                    track_id=tid,
                    class_name=cls_name,
                    class_id=cls_id,
                    confidence=conf,
                    bbox=bbox,
                    history=[[(x1 + x2) / 2, (y1 + y2) / 2]],
                )
                self._tracks[tid] = t

            active_tracks.append(self._tracks[tid])

        # Mark absent tracks as lost
        for tid, t in self._tracks.items():
            if tid not in active_ids:
                t.is_lost = True
                t.is_new = False

        return active_tracks

    def reset(self) -> None:
        self._tracks.clear()
        self._frame_idx = 0
        if BOXMOT_AVAILABLE:
            self.tracker = ByteTracker()


class SimpleIoUTracker:
    """Fallback IoU-based tracker when boxmot is not available.

    Suitable for low-frame-rate or single-class scenarios.
    """

    def __init__(self, iou_threshold: float = 0.3, max_lost: int = 10) -> None:
        self._tracks: dict[int, Track] = {}
        self._next_id = 1
        self._iou_threshold = iou_threshold
        self._max_lost = max_lost
        self._lost_counts: dict[int, int] = {}

    @staticmethod
    def _iou(a: list[float], b: list[float]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        union = area_a + area_b - inter + 1e-7
        return inter / union

    def update(self, detections: list[dict], frame_shape: tuple = (640, 640)) -> list[Track]:
        # Greedy match by IoU
        active_track_ids = list(self._tracks.keys())
        matched_det = set()
        matched_trk = set()

        for trk_id in active_track_ids:
            trk = self._tracks[trk_id]
            best_iou, best_det_idx = 0.0, -1
            for di, det in enumerate(detections):
                if di in matched_det:
                    continue
                iou = self._iou(trk.bbox, det["bbox"])
                if iou > best_iou:
                    best_iou, best_det_idx = iou, di
            if best_iou >= self._iou_threshold:
                det = detections[best_det_idx]
                trk.bbox = det["bbox"]
                trk.confidence = det["confidence"]
                trk.age += 1
                trk.is_new = False
                trk.is_lost = False
                trk.history.append(
                    [(det["bbox"][0] + det["bbox"][2]) / 2, (det["bbox"][1] + det["bbox"][3]) / 2]
                )
                matched_det.add(best_det_idx)
                matched_trk.add(trk_id)
                self._lost_counts[trk_id] = 0

        # New detections
        for di, det in enumerate(detections):
            if di in matched_det:
                continue
            tid = self._next_id
            self._next_id += 1
            cx = (det["bbox"][0] + det["bbox"][2]) / 2
            cy = (det["bbox"][1] + det["bbox"][3]) / 2
            self._tracks[tid] = Track(
                track_id=tid,
                class_name=det.get("class", ""),
                class_id=det.get("class_id", 0),
                confidence=det["confidence"],
                bbox=det["bbox"],
                history=[[cx, cy]],
            )
            self._lost_counts[tid] = 0

        # Handle lost tracks
        to_remove = []
        for trk_id in active_track_ids:
            if trk_id not in matched_trk:
                self._tracks[trk_id].is_lost = True
                self._tracks[trk_id].is_new = False
                self._lost_counts[trk_id] = self._lost_counts.get(trk_id, 0) + 1
                if self._lost_counts[trk_id] > self._max_lost:
                    to_remove.append(trk_id)
        for trk_id in to_remove:
            del self._tracks[trk_id]
            del self._lost_counts[trk_id]

        return [t for t in self._tracks.values() if not t.is_lost]


def get_tracker(
    tracker_type: str = "bytetrack",
    **kwargs,
) -> "ByteTrackWrapper | SimpleIoUTracker":
    """Factory — returns ByteTrackWrapper if boxmot available, else SimpleIoUTracker."""
    if tracker_type == "bytetrack" and BOXMOT_AVAILABLE:
        return ByteTrackWrapper(**kwargs)
    return SimpleIoUTracker(**kwargs)
