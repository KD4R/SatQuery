"""
services/celery_orchestrator.py — Shared Celery application entrypoint.

The compose workers start with ``celery -A services.celery_orchestrator``.
Before P6 this module did not exist (every worker container crash-looped with
"Unable to load celery application"), and each service defined its own private
Celery app while producers called ``.delay()`` on the default queue — so the
named queues in docker-compose (ingest/analysis/report) never received work.

This module is the single app both producers and workers resolve:
  - producers: task objects registered here route via ``task_routes`` below
  - workers:   started with -A on this module, consuming named + default queues

OWASP A04 note: acks_late + prefetch 1 prevents task loss / head-of-line
blocking; eager mode keeps tests hermetic without a broker.
"""

import os

from celery import Celery

from packages.providers.config import config

celery_app = Celery(
    "satquery",
    broker=config.redis_url.get_secret_value(),
    backend=config.redis_url.get_secret_value(),
)

# In test environments, run tasks synchronously (same contract the per-service
# modules honored before consolidation).
if os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() == "true":
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,  # Prevent task loss on worker crash
    worker_prefetch_multiplier=1,  # One task per worker to avoid blocking
    # Route the real tasks onto the compose worker queues. Everything else
    # falls through to the default `celery` queue, which every worker also
    # consumes (see docker-compose commands).
    task_routes={
        "services.geo.implementation.process_geo_job": {"queue": "ingest"},
        "services.agent.worker.process_agent_run": {"queue": "analysis"},
    },
)

# Import the modules that define tasks so they register on this app.
celery_app.conf.update(
    include=[
        "services.geo.implementation",
        "services.agent.worker",
    ]
)
