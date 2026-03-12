"""Abstract base class for all workflow nodes."""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional


class NodeOutput:
    """Typed container passed between nodes."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __repr__(self) -> str:
        return f"NodeOutput({list(self.data.keys())})"


class BaseNode(ABC):
    """Every node must implement process() which receives upstream outputs."""

    node_type: str = "base"

    def __init__(self, node_id: str, config: dict[str, Any]) -> None:
        self.node_id = node_id
        self.config = config

    async def setup(self) -> None:
        """Called once before the workflow starts (open connections, load models, etc.)."""

    async def teardown(self) -> None:
        """Called when the workflow stops."""

    @abstractmethod
    async def process(self, inputs: dict[str, NodeOutput]) -> Optional[NodeOutput]:
        """Perform node computation and return output (or None to stop propagation)."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.node_id})"
