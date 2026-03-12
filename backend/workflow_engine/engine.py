"""Workflow execution engine: builds a DAG from a ReactFlow-compatible graph definition
and executes it frame-by-frame in topological order.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

try:
    import networkx as nx
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False

from .nodes import BaseNode, NodeOutput, NODE_REGISTRY

logger = logging.getLogger(__name__)


def _build_graph(workflow_def: dict) -> "nx.DiGraph":
    """Parse a ReactFlow-style graph JSON into a networkx DiGraph.

    Expected format:
    {
        "nodes": [{"id": "n1", "type": "DetectObjects", "data": {...config...}}],
        "edges": [{"source": "n1", "target": "n2"}]
    }
    """
    if not NX_AVAILABLE:
        raise RuntimeError("networkx is not installed: pip install networkx")
    g = nx.DiGraph()
    for node in workflow_def.get("nodes", []):
        g.add_node(node["id"], type=node["type"], config=node.get("data", {}))
    for edge in workflow_def.get("edges", []):
        g.add_edge(edge["source"], edge["target"])
    return g


def _instantiate_nodes(graph: "nx.DiGraph") -> dict[str, BaseNode]:
    nodes: dict[str, BaseNode] = {}
    for node_id, attrs in graph.nodes(data=True):
        node_type = attrs.get("type", "")
        config = attrs.get("config", {})
        cls = NODE_REGISTRY.get(node_type)
        if cls is None:
            raise ValueError(f"Unknown node type: {node_type!r}")
        nodes[node_id] = cls(node_id=node_id, config=config)
    return nodes


class WorkflowExecutor:
    """Runs a workflow DAG: one call to run_frame() per input frame."""

    def __init__(self, workflow_def: dict) -> None:
        self.graph = _build_graph(workflow_def)
        self.node_instances = _instantiate_nodes(self.graph)
        self._sorted_ids: list[str] = list(nx.topological_sort(self.graph)) if NX_AVAILABLE else []
        self._running = False

    async def setup(self) -> None:
        """Call setup() on all nodes (open connections, load models)."""
        for node_id in self._sorted_ids:
            node = self.node_instances[node_id]
            try:
                await node.setup()
            except Exception as exc:
                logger.warning("Node %s setup failed: %s", node_id, exc)
        self._running = True

    async def teardown(self) -> None:
        """Tear down all nodes gracefully."""
        self._running = False
        for node_id in reversed(self._sorted_ids):
            node = self.node_instances[node_id]
            try:
                await node.teardown()
            except Exception as exc:
                logger.warning("Node %s teardown failed: %s", node_id, exc)

    async def run_frame(self, initial_data: Optional[dict] = None) -> dict[str, Any]:
        """Execute one complete pass through the DAG.

        Args:
            initial_data: Optional extra data merged into the first source node's output.

        Returns:
            Dictionary mapping node_id → output data dict (or None if node produced no output).
        """
        node_outputs: dict[str, Optional[NodeOutput]] = {}

        for node_id in self._sorted_ids:
            node = self.node_instances[node_id]
            # Collect outputs from upstream predecessors
            predecessors = list(self.graph.predecessors(node_id))
            if predecessors:
                inputs = {
                    pred_id: node_outputs[pred_id]
                    for pred_id in predecessors
                    if node_outputs.get(pred_id) is not None
                }
            else:
                # Source node — no upstream inputs
                inputs = {}
                if initial_data:
                    inputs["__init__"] = NodeOutput(initial_data)

            # Skip node if any required upstream produced nothing
            if predecessors and not inputs:
                node_outputs[node_id] = None
                continue

            try:
                output = await node.process(inputs)
            except Exception as exc:
                logger.error("Node %s raised during process(): %s", node_id, exc, exc_info=True)
                output = None

            node_outputs[node_id] = output

        return {k: (v.data if v else None) for k, v in node_outputs.items()}

    async def run_forever(self, fps: float = 30.0, on_frame_callback=None) -> None:
        """Run the workflow in a continuous loop until stopped.

        Args:
            fps: Target frames-per-second (used to throttle the loop).
            on_frame_callback: Optional async callable(frame_outputs) called each iteration.
        """
        interval = 1.0 / fps
        while self._running:
            start = asyncio.get_event_loop().time()
            outputs = await self.run_frame()
            if on_frame_callback:
                try:
                    await on_frame_callback(outputs)
                except Exception as exc:
                    logger.error("on_frame_callback raised: %s", exc)
            elapsed = asyncio.get_event_loop().time() - start
            sleep_time = max(0.0, interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    @property
    def is_running(self) -> bool:
        return self._running

    def get_node_types(self) -> list[str]:
        """Return the node type string for each node in topological order."""
        return [
            self.graph.nodes[nid].get("type", "unknown")
            for nid in self._sorted_ids
        ]
