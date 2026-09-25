import logging
import redis
from packages.providers.config import config
from services.agent.graph.orchestrator import get_orchestrator
from services.celery_orchestrator import celery_app

logger = logging.getLogger(__name__)

# Implements P2-04: Async agent execute endpoint and run orchestration
# Task registers on the shared SatQuery Celery app (services.celery_orchestrator),
# which provides broker/backend config, eager-mode test support, and routes
# this task to the `analysis` queue consumed by worker-analysis.

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

redis_client = redis.from_url(config.redis_url.get_secret_value(), decode_responses=True)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_agent_run(self, job_id: str):
    """
    Executes the LangGraph mission orchestration synchronously within the worker process.
    """
    logger.info(f"Starting Agent Run {job_id}")

    orchestrator = get_orchestrator()
    state = orchestrator.get_run(job_id)
    if not state:
        logger.error(f"Run {job_id} not found in orchestrator memory.")
        return {"status": "failed", "reason": "run_not_found", "job_id": job_id}

    import json

    channel = f"mission:{state.mission_id}:status"

    try:
        final_state = state
        for event in orchestrator._app.stream(state):
            node_name = list(event.keys())[0]
            node_state = event[node_name]
            status_val = node_state.get("status", node_name)

            # Publish to Redis
            try:
                redis_client.publish(
                    channel,
                    json.dumps(
                        {"status": status_val, "node": node_name, "agent_state": node_state}
                    ),
                )
            except Exception as e:
                logger.warning(f"Failed to publish status update: {e}")

            # Merge partial state into final_state
            final_state.status = status_val
            for k, v in node_state.items():
                setattr(final_state, k, v)

        if final_state.status != "FAILED":
            final_state.status = "COMPLETED"

        orchestrator._runs[job_id] = final_state
        return {"status": "success", "job_id": job_id, "final_status": final_state.status}
    except Exception as e:
        logger.error(f"Agent run {job_id} failed: {e}")
        state.status = "FAILED"
        state.errors.append(str(e))
        raise self.retry(exc=e)
