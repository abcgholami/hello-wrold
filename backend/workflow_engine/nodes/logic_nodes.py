"""Logic / control-flow nodes: FilterByClass, FilterByConfidence, Conditional, Throttle, Aggregate."""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any, Optional

from .base_node import BaseNode, NodeOutput


class FilterByClass(BaseNode):
    """Keep only detections matching specified class names."""

    node_type = "FilterByClass"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.classes: list[str] = config.get("classes", [])

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        detections = upstream.get("detections", [])
        filtered = [d for d in detections if d.get("class") in self.classes]
        if not filtered:
            return None
        return NodeOutput({**upstream.data, "detections": filtered})


class FilterByConfidence(BaseNode):
    """Keep only detections above a confidence threshold."""

    node_type = "FilterByConfidence"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.threshold: float = float(config.get("threshold", 0.5))

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        detections = upstream.get("detections", [])
        filtered = [d for d in detections if d.get("confidence", 0.0) >= self.threshold]
        if not filtered:
            return None
        return NodeOutput({**upstream.data, "detections": filtered})


class Conditional(BaseNode):
    """Route output to either the 'true' or 'false' branch based on a condition.

    Config:
        condition_field: e.g. "count"
        operator: "gt" | "lt" | "gte" | "lte" | "eq" | "neq"
        value: numeric threshold
    """

    node_type = "Conditional"

    _OPS = {
        "gt": lambda a, b: a > b,
        "lt": lambda a, b: a < b,
        "gte": lambda a, b: a >= b,
        "lte": lambda a, b: a <= b,
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
    }

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.field: str = config.get("condition_field", "count")
        self.operator: str = config.get("operator", "gt")
        self.threshold: float = float(config.get("value", 0))
        self.result: Optional[bool] = None

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        field_value = upstream.get(self.field, 0)
        op_fn = self._OPS.get(self.operator, lambda a, b: a > b)
        self.result = op_fn(field_value, self.threshold)
        return NodeOutput({**upstream.data, "condition_result": self.result})


class Throttle(BaseNode):
    """Rate-limit output to at most N events per second."""

    node_type = "Throttle"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.rate: float = float(config.get("rate", 1.0))
        self._last_emit: float = 0.0

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        now = time.monotonic()
        if now - self._last_emit < 1.0 / self.rate:
            return None
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        self._last_emit = now
        return NodeOutput(upstream.data)


class Aggregate(BaseNode):
    """Accumulate data over a time window and emit summary statistics."""

    node_type = "Aggregate"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        super().__init__(node_id, config)
        self.window_seconds: float = float(config.get("window_seconds", 60.0))
        self.field: str = config.get("field", "count")
        self._buffer: deque = deque()

    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        upstream = next(iter(inputs.values()), None)
        if upstream is None:
            return None
        now = time.monotonic()
        value = upstream.get(self.field)
        if value is not None:
            self._buffer.append((now, value))
        # Evict old entries
        while self._buffer and (now - self._buffer[0][0]) > self.window_seconds:
            self._buffer.popleft()

        values = [v for _, v in self._buffer]
        if not values:
            return None

        summary = {
            "count": len(values),
            "sum": sum(values),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "window_seconds": self.window_seconds,
        }
        return NodeOutput({**upstream.data, "aggregate": summary})
