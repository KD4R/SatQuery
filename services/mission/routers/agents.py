"""
services/mission/routers/agents.py — Integration stubs for AI Agents (P1-15).

Agents hook into the pipeline here to report status and submit ML results.
Must be authenticated with SYSTEM role or agent:write S2S scope.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from packages.auth import get_tenant_id, require_role
from packages.auth.models import AuthContext, Role
from services.mission.domain.models import JobStatus
from services.mission.domain.schemas import AgentJobUpdate, JobStatusResponse
from services.mission.repositories.base import JobRepository
from services.mission.dependencies import get_job_repo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents"])


@router.patch("/api/v1/jobs/{job_id}/agent-status", response_model=JobStatusResponse)
async def update_job_from_agent(
    job_id: str,
    update_data: AgentJobUpdate,
    ctx: AuthContext = Depends(require_role(Role.SYSTEM)),
    org_id: str = Depends(get_tenant_id),
    job_repo: JobRepository = Depends(get_job_repo),
) -> JobStatusResponse:
    """
    Called by an external AI Agent to report progress or completion of a job.
    Requires SYSTEM privileges (e.g. an internal service token).
    """
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

    # Apply updates
    job.status = update_data.status
    if update_data.error_message:
        job.error_message = update_data.error_message

    if update_data.status == JobStatus.RUNNING and job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    elif update_data.status in (JobStatus.COMPLETED, JobStatus.FAILED):
        job.completed_at = datetime.now(timezone.utc)

    # In a real system, we might also save update_data.result_data into a Results table
    # For now, we update the job record.
    updated_job = await job_repo.update(job)

    logger.info(
        "Agent updated job %s in org %s. status=%s progress=%s",
        job_id,
        org_id,
        update_data.status.value,
        update_data.progress,
    )

    return JobStatusResponse(
        job_id=updated_job.id,
        mission_id=updated_job.mission_id,
        status=updated_job.status,
        submitted_at=updated_job.submitted_at,
        started_at=updated_job.started_at,
        completed_at=updated_job.completed_at,
        error_message=updated_job.error_message,
        trace_id=updated_job.trace_id,
    )
