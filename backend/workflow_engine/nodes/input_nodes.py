"""Input nodes: CameraCapture, RTSPStream, VideoFile, ImageFolder."""
from __future__ import annotations

import asyncio
import base64
import io
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import cv2
import numpy as np

from .base_node import BaseNode, NodeOutput


class CameraCapture(BaseNode):
    """Capture frames from a local webcam device."""

    node_type = "CameraCapture"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.device_index: int = int(config.get("device_index", 0))
        self.fps: float = float(config.get("fps", 30.0))
        self._cap: Optional[cv2.VideoCapture] = None

    async def setup(self) -> None:
        self._cap = cv2.VideoCapture(self.device_index)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)

    async def teardown(self) -> None:
        if self._cap and self._cap.isOpened():
            self._cap.release()

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        if self._cap is None or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        if not ret:
            return None
        return NodeOutput({"frame": frame, "source": "camera", "device": self.device_index})


class RTSPStream(BaseNode):
    """Capture frames from an RTSP stream URL."""

    node_type = "RTSPStream"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.url: str = config["url"]
        self.fps: float = float(config.get("fps", 10.0))
        self._cap: Optional[cv2.VideoCapture] = None

    async def setup(self) -> None:
        # Use FFMPEG backend for RTSP
        self._cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)

    async def teardown(self) -> None:
        if self._cap and self._cap.isOpened():
            self._cap.release()

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        if self._cap is None or not self._cap.isOpened():
            return None
        loop = asyncio.get_event_loop()
        ret, frame = await loop.run_in_executor(None, self._cap.read)
        if not ret:
            return None
        return NodeOutput({"frame": frame, "source": "rtsp", "url": self.url})


class VideoFile(BaseNode):
    """Read frames from a video file (from a local path or bytes from workflow config)."""

    node_type = "VideoFile"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.path: str = config["path"]
        self.loop: bool = bool(config.get("loop", False))
        self._cap: Optional[cv2.VideoCapture] = None

    async def setup(self) -> None:
        self._cap = cv2.VideoCapture(self.path)

    async def teardown(self) -> None:
        if self._cap and self._cap.isOpened():
            self._cap.release()

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        if not ret:
            if self.loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if not ret:
                    return None
            else:
                return None
        return NodeOutput({"frame": frame, "source": "video_file", "path": self.path})


class WebSocketFrameSource(BaseNode):
    """Receive base64-encoded frames from a WebSocket connection (browser camera)."""

    node_type = "WebSocketFrameSource"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10)

    def push_frame(self, frame_b64: str) -> None:
        """Called externally by the WebSocket handler to push a new frame."""
        if not self._queue.full():
            self._queue.put_nowait(frame_b64)

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        try:
            frame_b64 = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
        img_bytes = base64.b64decode(frame_b64)
        arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None
        return NodeOutput({"frame": frame, "source": "websocket"})
