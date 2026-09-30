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


def _stream_run(job_id: str) -> dict:
    """
    Stream one agent run through the LangGraph, publishing each node's status to
    the mission's Redis channel (what the gateway's WS bridges) and persisting
    each partial state to the Redis run store so any process can read it.

    Shared by the Celery task below and the API route's in-process executor —
    the publish/persist behaviour must not depend on which process runs the graph.
    """
    orchestrator = get_orchestrator()
    state = orchestrator.get_run(job_id)
    if not state:
        logger.error("Run %s not found in the run store.", job_id)
        return {"status": "failed", "reason": "run_not_found", "job_id": job_id}

    import json
    from datetime import datetime, timezone

    from services.agent.graph.run_inputs import redact_signed_urls

    channel = f"mission:{state.mission_id}:status"

    final_state = state
    status_val = state.status
    try:
        for event in orchestrator._app.stream(state):
            node_name = list(event.keys())[0]
            node_state = event[node_name]
            status_val = node_state.get("status", node_name)

            # Merge partial state first, so what is published and what is stored
            # describe the same moment.
            for k, v in node_state.items():
                setattr(final_state, k, v)
            final_state.status = status_val
            final_state.updated_at = datetime.now(timezone.utc)

            # Persist after every node: the polling route (and any other process)
            # sees the run advance instead of INITIALIZED until the very end.
            orchestrator.save_run(final_state)

            # Publish to the mission channel the gateway WS bridges. Signed asset
            # URLs (SAS tokens) are stripped: the browser never needs them.
            try:
                redis_client.publish(
                    channel,
                    json.dumps(
                        {
                            "status": status_val,
                            "node": node_name,
                            "agent_state": redact_signed_urls(node_state),
                        },
                        default=str,
                    ),
                )
            except Exception as e:  # noqa: BLE001 — streaming must not die on a publish hiccup
                logger.warning("Failed to publish status update: %s", e)

        if final_state.status not in ("FAILED", "COMPLETED"):
            # The graph always ends in synthesize, which sets one of the two; any
            # other value here means a node returned an unexpected status.
            final_state.status = "FAILED"
            final_state.errors.append(f"Run ended in unexpected state {status_val!r}")

        orchestrator.save_run(final_state)
        return {"status": "success", "job_id": job_id, "final_status": final_state.status}
    except Exception as e:
        logger.exception("Agent run %s failed", job_id)
        final_state.status = "FAILED"
        final_state.errors.append(str(e))
        # Persist the failure: an unsaved FAILED leaves pollers seeing the last
        # intermediate status until they time out.
        try:
            orchestrator.save_run(final_state)
        except Exception:  # noqa: BLE001
            logger.exception("Could not persist failed state for %s", job_id)
        raise


@celery_app.task(bind=True, max_retries=0)
def process_agent_run(self, job_id: str):
    """
    Executes the LangGraph mission orchestration synchronously within the worker process.

    Not retried: a failure is recorded on the run (status FAILED + error) and a
    blind retry would re-run satellite search and inference for a run the user
    has already been told failed. The user can start a new run.
    """
    logger.info("Starting Agent Run %s", job_id)
    return _stream_run(job_id)
