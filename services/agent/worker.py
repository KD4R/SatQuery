import logging
from celery import Celery
import redis
import os
from packages.providers.config import config
from services.agent.graph.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)

# Implements P2-04: Async agent execute endpoint and run orchestration
celery_app = Celery(
    "agent_worker",
    broker=config.redis_url.get_secret_value(),
    backend=config.redis_url.get_secret_value(),
)

# In test environments, run tasks synchronously
if os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() == "true":
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)

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

    try:
        final_state = orchestrator.step_execution(state)
        return {"status": "success", "job_id": job_id, "final_status": final_state.status}
    except Exception as e:
        logger.error(f"Agent run {job_id} failed: {e}")
        state.status = "FAILED"
        state.errors.append(str(e))
        raise self.retry(exc=e)
