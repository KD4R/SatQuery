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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from packages.auth import get_tenant_id, require_role
from packages.auth.models import AuthContext, Role
from services.mission.domain.models import Job, JobStatus, MissionStatus
from services.mission.domain.schemas import JobStatusResponse, JobSubmitResponse
from services.mission.repositories.base import JobRepository, MissionRepository
from services.mission.dependencies import get_job_repo, get_mission_repo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])


async def _run_job_background(job: Job, job_repo: JobRepository) -> None:
    """
    Simulate async job execution — in production this hands off to Celery/Redis.
    Marked RUNNING → COMPLETED in background.
    """
    from datetime import datetime, timezone

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    await job_repo.update(job)
    # Real impl: producer.send(topic="mission.run", value=job.id)
    # For now mark completed synchronously so tests can assert on it
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(timezone.utc)
    await job_repo.update(job)
    logger.info("Job completed (background): job_id=%s mission_id=%s", job.id, job.mission_id)


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
    background_tasks.add_task(_run_job_background, created_job, job_repo)

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
