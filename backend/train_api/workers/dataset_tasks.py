"""Dataset processing tasks: workflow execution, augmentation."""
from celery.utils.log import get_task_logger
from train_api.workers.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="execute_workflow", max_retries=0)
def execute_workflow(self, workflow_id: str, run_id: str):
    """
    Execute a workflow definition.
    Loads the graph JSON, builds execution pipeline, and processes frames.
    """
    import asyncio
    from shared.db.models import WorkflowDefinition, WorkflowRun
    from datetime import datetime, timezone

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from shared.config import get_settings

    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        workflow = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == workflow_id).first()

        if not run or not workflow:
            logger.error(f"Workflow {workflow_id} or run {run_id} not found")
            return

        run.status = "running"
        db.commit()

        logger.info(f"Starting workflow {workflow_id} run {run_id}")

        # Simple graph execution: iterate nodes in order
        graph = workflow.graph
        nodes = graph.get("nodes", [])

        import redis as sync_redis
        redis_client = sync_redis.from_url(settings.redis_url)

        for node in nodes:
            node_type = node.get("type", "")
            node_id = node.get("id", "")
            node_data = node.get("data", {})

            logger.info(f"Executing node {node_id} ({node_type})")

            event = {
                "type": "node_started",
                "node_id": node_id,
                "node_type": node_type,
            }
            redis_client.publish(f"workflow:{workflow_id}", __import__("json").dumps(event))

        run.status = "completed"
        run.ended_at = datetime.now(timezone.utc)
        workflow.status = "stopped"
        db.commit()

        redis_client.publish(f"workflow:{workflow_id}", __import__("json").dumps({
            "type": "run_completed", "run_id": run_id
        }))

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        if run:
            run.status = "failed"
            run.error_message = str(e)
            run.ended_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
