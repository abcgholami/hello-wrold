"""Workflow scheduler: manages running WorkflowExecutor instances per workflow_id."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .engine import WorkflowExecutor

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """Singleton that tracks running workflow executors.

    Each workflow runs as an asyncio Task in the background.
    """

    def __init__(self) -> None:
        self._executors: dict[str, WorkflowExecutor] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def start_workflow(
        self,
        workflow_id: str,
        workflow_def: dict,
        fps: float = 30.0,
        on_frame_callback=None,
    ) -> None:
        """Start a workflow if not already running."""
        if workflow_id in self._tasks and not self._tasks[workflow_id].done():
            logger.info("Workflow %s is already running", workflow_id)
            return

        executor = WorkflowExecutor(workflow_def)
        await executor.setup()
        self._executors[workflow_id] = executor

        task = asyncio.create_task(
            executor.run_forever(fps=fps, on_frame_callback=on_frame_callback),
            name=f"workflow-{workflow_id}",
        )
        self._tasks[workflow_id] = task
        logger.info("Started workflow %s", workflow_id)

    async def stop_workflow(self, workflow_id: str) -> None:
        """Stop a running workflow gracefully."""
        executor = self._executors.get(workflow_id)
        if executor:
            await executor.teardown()

        task = self._tasks.get(workflow_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._executors.pop(workflow_id, None)
        self._tasks.pop(workflow_id, None)
        logger.info("Stopped workflow %s", workflow_id)

    def is_running(self, workflow_id: str) -> bool:
        task = self._tasks.get(workflow_id)
        return task is not None and not task.done()

    def list_running(self) -> list[str]:
        return [wid for wid, task in self._tasks.items() if not task.done()]

    async def stop_all(self) -> None:
        for workflow_id in list(self._tasks.keys()):
            await self.stop_workflow(workflow_id)


# Module-level singleton accessible from FastAPI lifespan
scheduler = WorkflowScheduler()
