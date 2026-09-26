"""
services/mission/routers/jobs.py — Async job lifecycle bridge (P1-07).

Routes:
  POST /api/v1/missions/{id}/runs  Submit a mission run    (OPERATOR+)
  GET  /api/v1/jobs/{job_id}       Poll job status         (VIEWER+)

P1-07 contract:
  - Submission is fire-and-forget: returns 202 Accepted + job_id immediately.
  - The actual ML inference is enqueued to a worker queue (Celery/Redis in prod).
  - In this implementation the queue is an in-memory async queue (testable).
  - Polling endpoint returns current JobStatus.

OWASP:
  A04 — Mission ownership verified before job submission.
  A01 — OPERATOR minimum to submit; VIEWER to poll.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from packages.shared.client import InternalClient

from packages.auth import get_tenant_id, require_role
from packages.auth.models import AuthContext, Role
from services.mission.domain.models import Job, JobStatus, MissionStatus
from services.mission.domain.schemas import JobStatusResponse, JobSubmitResponse
from services.mission.repositories.base import JobRepository, MissionRepository
from services.mission.dependencies import get_job_repo, get_mission_repo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])


AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8002")


async def _run_job_background(
    job: Job,
    mission_query: str,
    job_repo: JobRepository,
    mission_repo: MissionRepository,
) -> None:
    """
    Simulate async job execution — in production this hands off to Celery/Redis.
    Marked RUNNING → COMPLETED in background.
    Now we actually call the Agent service via InternalClient.
    """
    import asyncio
    from datetime import datetime, timezone

    from packages.auth.models import AuthContext
    from packages.shared.client import CircuitBreakerOpenError, InternalClientError

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    await job_repo.update(job)

    # Initialize InternalClient to talk to Agent
    client = InternalClient(
        base_url=AGENT_SERVICE_URL, caller_service="mission", scopes=["agent:write"]
    )

    # We construct a mock auth context representing the system for the internal call.
    system_ctx = AuthContext(
        subject=f"system:mission:{job.mission_id}",
        email=None,
        organisation_id=job.organisation_id,
        roles=[Role.SYSTEM],
        trace_id=job.trace_id or "",
    )

    agent_job_id: Optional[str] = None
    try:
        # Trigger the LangGraph agent run
        response = await client.post(
            "/api/v1/agent/execute",
            auth_context=system_ctx,
            json={"mission_id": job.mission_id, "query": mission_query},
        )
        agent_job_id = response.json().get("job_id")
        logger.info(
            "Successfully dispatched job_id=%s to Agent service (agent job %s).",
            job.id,
            agent_job_id,
        )
    except Exception as exc:
        logger.error("Failed to dispatch job_id=%s to Agent: %s", job.id, exc)
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = f"Agent invocation failed: {str(exc)}"
        await job_repo.update(job)
        await client.aclose()
        return

    # The agent executes the graph in its own process; its /runs/{job_id} route
    # reports terminal state. Poll so the operator's job record reaches a
    # terminal status too — a job stuck RUNNING forever is a lie on the timeline.
    terminal: Optional[dict] = None
    for _ in range(180):  # bounded: 180 x 1s ≈ 3 min ceiling for one run
        await asyncio.sleep(1)
        try:
            run_response = await client.get(
                f"/api/v1/agent/runs/{agent_job_id}", auth_context=system_ctx
            )
            run_status = str(run_response.json().get("status", "")).upper()
            if run_status in ("COMPLETED", "FAILED"):
                terminal = run_response.json()
                break
        except InternalClientError as exc:
            # 404 until the agent stores the run? create_run stores synchronously,
            # so a 404 here means a real routing problem — fail the job.
            if exc.status_code == 404:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = "Agent reported no such run after dispatch."
                await job_repo.update(job)
                await client.aclose()
                return
        except (CircuitBreakerOpenError, Exception) as exc:  # noqa: BLE001 — keep polling
            logger.warning("Polling agent run %s failed: %s", agent_job_id, exc)

    # Resolve the mission alongside the job so the missions list never shows a
    # run as "completed" while its mission still reads "queued".
    mission = await mission_repo.get_by_id(job.mission_id, job.organisation_id)
    if terminal is None:
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = "Agent run did not reach a terminal state in time."
        await job_repo.update(job)
        if mission:
            mission.status = MissionStatus.FAILED
            await mission_repo.update(mission)
    elif terminal.get("status", "").upper() == "COMPLETED":
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        await job_repo.update(job)
        if mission:
            mission.status = MissionStatus.COMPLETED
            await mission_repo.update(mission)
    else:
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        errors = terminal.get("errors") or []
        job.error_message = "; ".join(str(e) for e in errors) or "Agent run failed."
        await job_repo.update(job)
        if mission:
            mission.status = MissionStatus.FAILED
            await mission_repo.update(mission)

    await client.aclose()


@router.post(
    "/api/v1/missions/{mission_id}/runs",
    status_code=202,
    response_model=JobSubmitResponse,
)
async def submit_mission_run(
    mission_id: str,
    background_tasks: BackgroundTasks,
    ctx: AuthContext = Depends(require_role(Role.OPERATOR)),
    org_id: str = Depends(get_tenant_id),
    mission_repo: MissionRepository = Depends(get_mission_repo),
    job_repo: JobRepository = Depends(get_job_repo),
) -> JobSubmitResponse:
    """
    Submit a new async run for a Mission. Returns 202 + job_id.
    The run is enqueued; poll /api/v1/jobs/{job_id} for status.
    """
    mission = await mission_repo.get_by_id(mission_id, org_id)
    if mission is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MISSION_NOT_FOUND",
                "message": f"Mission '{mission_id}' not found.",
                "retryable": False,
            },
        )

    if mission.status in (MissionStatus.RUNNING, MissionStatus.QUEUED):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MISSION_ALREADY_RUNNING",
                "message": "Mission already has an active run.",
                "retryable": False,
            },
        )

    # Transition mission to QUEUED
    mission.status = MissionStatus.QUEUED
    await mission_repo.update(mission)

    job = Job(
        mission_id=mission_id,
        organisation_id=org_id,
        submitted_by=ctx.subject,
        status=JobStatus.PENDING,
        trace_id=ctx.trace_id,
    )
    created_job = await job_repo.create(job)

    # Enqueue background processing
    mission_query = mission.description or mission.name
    background_tasks.add_task(
        _run_job_background, created_job, mission_query, job_repo, mission_repo
    )

    logger.info(
        "Job submitted: job_id=%s mission_id=%s org=%s subject=%s",
        created_job.id,
        mission_id,
        org_id,
        ctx.subject,
    )
    return JobSubmitResponse(
        job_id=created_job.id,
        mission_id=mission_id,
        status=created_job.status,
        submitted_at=created_job.submitted_at,
        trace_id=created_job.trace_id,
    )


@router.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    org_id: str = Depends(get_tenant_id),
    _: AuthContext = Depends(require_role(Role.VIEWER)),
    job_repo: JobRepository = Depends(get_job_repo),
) -> JobStatusResponse:
    """Poll the current status of a submitted Job."""
    job = await job_repo.get_by_id(job_id, org_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "JOB_NOT_FOUND",
                "message": f"Job '{job_id}' not found.",
                "retryable": False,
            },
        )
    return JobStatusResponse(
        job_id=job.id,
        mission_id=job.mission_id,
        status=job.status,
        submitted_at=job.submitted_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        trace_id=job.trace_id,
    )
