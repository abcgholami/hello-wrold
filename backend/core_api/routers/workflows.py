"""Workflow definition and execution endpoints with WebSocket live dashboard."""
import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.db.models import WorkflowDefinition, WorkflowRun, WorkflowEvent

router = APIRouter()


class WorkflowCreate(BaseModel):
    project_id: str
    name: str
    description: str | None = None
    graph: dict            # ReactFlow nodes+edges JSON
    schedule_cron: str | None = None


@router.post("", status_code=201)
async def create_workflow(data: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    wf = WorkflowDefinition(
        project_id=data.project_id,
        name=data.name,
        description=data.description,
        graph=data.graph,
        schedule_cron=data.schedule_cron,
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return {"id": wf.id, "name": wf.name, "status": wf.status}


@router.get("")
async def list_workflows(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.project_id == project_id))
    workflows = result.scalars().all()
    return [{"id": w.id, "name": w.name, "status": w.status, "created_at": w.created_at.isoformat()} for w in workflows]


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"id": wf.id, "name": wf.name, "graph": wf.graph, "status": wf.status}


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if "graph" in data:
        wf.graph = data["graph"]
    if "name" in data:
        wf.name = data["name"]
    if "schedule_cron" in data:
        wf.schedule_cron = data["schedule_cron"]
    await db.commit()
    return {"id": wf.id, "name": wf.name}


@router.post("/{workflow_id}/start")
async def start_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    """Start a workflow — creates a WorkflowRun and dispatches to Celery."""
    result = await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    run = WorkflowRun(workflow_id=workflow_id)
    db.add(run)
    wf.status = "running"
    await db.commit()
    await db.refresh(run)

    # Dispatch to Celery workflow engine
    from train_api.workers.celery_app import celery_app
    celery_app.send_task("execute_workflow", args=[workflow_id, run.id], queue="default")

    return {"run_id": run.id, "status": "running"}


@router.post("/{workflow_id}/stop")
async def stop_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    wf.status = "stopped"
    await db.commit()
    return {"id": workflow_id, "status": "stopped"}


@router.get("/{workflow_id}/runs")
async def list_runs(workflow_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(20)
    )
    runs = result.scalars().all()
    return [
        {"id": r.id, "status": r.status, "frames_processed": r.frames_processed,
         "started_at": r.started_at.isoformat() if r.started_at else None,
         "ended_at": r.ended_at.isoformat() if r.ended_at else None}
        for r in runs
    ]


@router.get("/runs/{run_id}/events")
async def list_run_events(run_id: str, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.workflow_run_id == run_id)
        .order_by(WorkflowEvent.occurred_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [
        {"id": e.id, "node_id": e.node_id, "event_type": e.event_type,
         "data": e.data, "occurred_at": e.occurred_at.isoformat()}
        for e in events
    ]


# ── WebSocket live dashboard ──────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, workflow_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(workflow_id, []).append(ws)

    def disconnect(self, workflow_id: str, ws: WebSocket):
        if workflow_id in self.active:
            self.active[workflow_id].remove(ws)

    async def broadcast(self, workflow_id: str, message: dict):
        for ws in self.active.get(workflow_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws/{workflow_id}")
async def workflow_ws(workflow_id: str, websocket: WebSocket):
    """Real-time workflow event stream for live dashboard."""
    import aioredis
    from shared.config import get_settings
    settings = get_settings()

    await websocket.accept()

    redis = await aioredis.from_url(settings.redis_url)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"workflow:{workflow_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"workflow:{workflow_id}")
        await redis.close()
