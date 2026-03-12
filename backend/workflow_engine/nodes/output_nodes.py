"""Output nodes: LiveDashboard, SaveToDB, TriggerAlert, ExportCSV, RobotOutput."""
from __future__ import annotations

import asyncio
import base64
import csv
import json
import socket
import time
from pathlib import Path
from typing import Any, Optional

import cv2
import httpx

from .base_node import BaseNode, NodeOutput


class LiveDashboard(BaseNode):
    """Push annotated frames + detection data to the browser via Redis Pub/Sub."""

    node_type = "LiveDashboard"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.workflow_id: str = config["workflow_id"]
        self.jpeg_quality: int = int(config.get("jpeg_quality", 75))
        self._redis = None

    async def setup(self) -> None:
        try:
            import aioredis
            from shared.config import settings
            self._redis = await aioredis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            self._redis = None

    async def teardown(self) -> None:
        if self._redis:
            await self._redis.close()

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None

        payload: dict[str, Any] = {"type": "frame", "timestamp": time.time()}

        frame = upstream.get("annotated_frame") or upstream.get("frame")
        if frame is not None:
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
            payload["frame_b64"] = base64.b64encode(buf.tobytes()).decode()

        for key in ("detections", "tracks", "count", "classification", "new_crossings"):
            val = upstream.get(key)
            if val is not None:
                payload[key] = val

        if self._redis:
            await self._redis.publish(f"workflow:{self.workflow_id}", json.dumps(payload))

        return NodeOutput(upstream.data)


class SaveToDB(BaseNode):
    """Persist detection events to the workflow_events table."""

    node_type = "SaveToDB"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.workflow_run_id: str = config.get("workflow_run_id", "")
        self.event_type: str = config.get("event_type", "detection")
        self._db_session = None

    async def setup(self) -> None:
        try:
            from shared.db.models import WorkflowEvent
            from shared.db.session import get_session
            self._WorkflowEvent = WorkflowEvent
            self._get_session = get_session
        except Exception:
            self._WorkflowEvent = None

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        if self._WorkflowEvent is None:
            return NodeOutput(upstream.data)

        event_data = {}
        for key in ("detections", "tracks", "count", "classification", "new_crossings"):
            val = upstream.get(key)
            if val is not None:
                event_data[key] = val

        try:
            async with self._get_session() as session:
                event = self._WorkflowEvent(
                    workflow_run_id=self.workflow_run_id or None,
                    node_id=self.node_id,
                    event_type=self.event_type,
                    data=event_data,
                )
                session.add(event)
                await session.commit()
        except Exception:
            pass

        return NodeOutput(upstream.data)


class TriggerAlert(BaseNode):
    """Send a webhook / Slack / email notification when triggered."""

    node_type = "TriggerAlert"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.webhook_url: str = config.get("webhook_url", "")
        self.message_template: str = config.get("message", "VisionForge alert: {count} objects detected")
        self.cooldown_seconds: float = float(config.get("cooldown_seconds", 60.0))
        self._last_alert: float = 0.0

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None

        # Only fire if condition_result is True (or not present)
        cond = upstream.get("condition_result", True)
        if not cond:
            return NodeOutput(upstream.data)

        now = time.monotonic()
        if now - self._last_alert < self.cooldown_seconds:
            return NodeOutput(upstream.data)

        self._last_alert = now
        message = self.message_template.format(**{k: upstream.get(k, "") for k in ["count", "class", "confidence"]})

        if self.webhook_url:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(self.webhook_url, json={"text": message, "data": upstream.data})
            except Exception:
                pass

        return NodeOutput({**upstream.data, "alert_sent": True, "alert_message": message})


class ExportCSV(BaseNode):
    """Append detection/counting events to a rolling CSV file."""

    node_type = "ExportCSV"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.output_path: str = config.get("output_path", "/tmp/workflow_export.csv")
        self._file = None
        self._writer = None

    async def setup(self) -> None:
        self._file = open(self.output_path, "a", newline="")
        self._writer = csv.writer(self._file)
        # Write header if file is empty
        if Path(self.output_path).stat().st_size == 0:
            self._writer.writerow(["timestamp", "count", "class", "confidence", "detections"])

    async def teardown(self) -> None:
        if self._file:
            self._file.close()

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        if self._writer is None:
            return NodeOutput(upstream.data)
        self._writer.writerow([
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            upstream.get("count", ""),
            upstream.get("class", ""),
            upstream.get("confidence", ""),
            json.dumps(upstream.get("detections", [])),
        ])
        self._file.flush()
        return NodeOutput(upstream.data)


class RobotOutput(BaseNode):
    """Emit detection data to a robot via TCP socket or UDP."""

    node_type = "RobotOutput"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.host: str = config.get("host", "localhost")
        self.port: int = int(config.get("port", 5555))
        self.protocol: str = config.get("protocol", "tcp").lower()
        self._sock: Optional[socket.socket] = None

    async def setup(self) -> None:
        if self.protocol == "udp":
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(2.0)
                self._sock.connect((self.host, self.port))
                self._sock.setblocking(False)
            except Exception:
                self._sock = None

    async def teardown(self) -> None:
        if self._sock:
            self._sock.close()

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        if self._sock is None:
            return NodeOutput(upstream.data)

        detections = upstream.get("detections", [])
        payload_items = []
        for det in detections:
            bbox = det.get("bbox", [0, 0, 0, 0])
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            payload_items.append({
                "class": det.get("class"),
                "confidence": det.get("confidence"),
                "center_x": center_x,
                "center_y": center_y,
                "bbox": bbox,
            })

        payload = json.dumps({"detections": payload_items, "timestamp": time.time()}) + "\n"
        data = payload.encode()

        try:
            loop = asyncio.get_event_loop()
            if self.protocol == "udp":
                await loop.sock_sendto(self._sock, data, (self.host, self.port))
            else:
                await loop.sock_sendall(self._sock, data)
        except Exception:
            pass

        return NodeOutput({**upstream.data, "robot_output_sent": True})
