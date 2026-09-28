"""
services/agent/app/api/routers/execute.py — Async agent execute router (P2-04).
"""

import logging
import os
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse


from services.agent.graph.orchestrator import get_orchestrator
from packages.auth.dependencies import get_current_user, require_role
from packages.auth.models import AuthContext, Role
from services.agent.schemas import ExecuteRequest, ExecuteResponse, MissionState
from services.agent.security.sanitizer import sanitize_prompt
from services.agent.security.tool_budget import ToolBudget
from services.agent.security.validator import validate_aoi_geometry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent-execute"])

# Run state lives in Redis (agent:run:{job_id}) behind the orchestrator's
# process-local cache, so a run created in this process is visible to every
# other consumer: the mission service polling GET /runs/{job_id}, the gateway
# WS bridging status, and a Celery worker if execution is enqueued there.
# By default the graph streams in this process (daemon thread); set
# AGENT_EXECUTION_MODE=celery to hand it to worker-analysis instead. Either way the
# publishes are what the gateway's mission WS bridges to the browser.


def _execute_run(job_id: str) -> None:
    """Stream one agent run in-process, publishing each node's status to Redis."""
    from services.agent.worker import _stream_run  # shared with the Celery task

    try:
        _stream_run(job_id)
    except Exception:  # noqa: BLE001 — background thread; log, never crash the app
        logger.exception("Background agent run failed: job_id=%s", job_id)


def _execution_mode() -> str:
    """``thread`` (default) or ``celery``, from AGENT_EXECUTION_MODE.

    thread  runs the graph in a daemon thread of this process. It needs no worker
            but is lost if the process restarts mid-run and cannot be scaled or
            retried.
    celery  enqueues ``process_agent_run`` for worker-analysis (durable, retried,
            horizontally scalable). Run state is in Redis, so the worker sees the
            run this process just created.

    Read per request so the mode can be flipped without a code change; anything
    unrecognised falls back to ``thread`` rather than dropping the run.
    """
    mode = os.getenv("AGENT_EXECUTION_MODE", "thread").strip().lower()
    return mode if mode in {"thread", "celery"} else "thread"


def _dispatch_run(job_id: str) -> None:
    """Start the run in the configured execution mode.

    Raises ``HTTPException(503)`` when the celery broker refuses the task: the
    caller has been promised a run, so a silent drop would leave it ``INITIALIZED``
    forever.
    """
    if _execution_mode() == "celery":
        from services.agent.worker import process_agent_run

        try:
            process_agent_run.delay(job_id)
        except Exception as exc:  # noqa: BLE001 — any broker fault means "not queued"
            logger.exception("Could not enqueue agent run %s", job_id)
            orchestrator = get_orchestrator()
            run = orchestrator.get_run(job_id)
            if run:
                run.status = "FAILED"
                run.errors.append(f"Run could not be queued: {exc}")
                orchestrator.save_run(run)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "QUEUE_UNAVAILABLE",
                    "message": "The analysis queue is unavailable; the run was not started.",
                    "retryable": True,
                },
            )
        return

    threading.Thread(
        target=_execute_run, args=(job_id,), name=f"agent-run-{job_id}", daemon=True
    ).start()


@router.post("/execute", status_code=status.HTTP_202_ACCEPTED, response_model=ExecuteResponse)
async def execute_agent(
    payload: ExecuteRequest,
    request: Request,
    ctx: AuthContext = Depends(get_current_user),
    _: AuthContext = Depends(require_role(Role.ANALYST)),
):
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")
    clean_query = sanitize_prompt(payload.query)
    if payload.aoi:
        validate_aoi_geometry(payload.aoi)

    # Normalise the client-supplied budget at the API edge: only the two
    # limit fields are accepted, and server-side ceilings apply (a caller may
    # request a smaller budget, never a larger one). Invalid or abusive
    # budgets are rejected here with 422 instead of exploding in the worker.
    budget_dict = None
    if payload.budget:
        try:
            budget = ToolBudget(
                max_calls=int(payload.budget.get("max_calls", ToolBudget().max_calls)),
                max_duration_seconds=float(
                    payload.budget.get("max_duration_seconds", ToolBudget().max_duration_seconds)
                ),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_BUDGET",
                    "message": f"Invalid tool budget: {exc}",
                    "retryable": False,
                },
            )
        budget_dict = {
            "max_calls": budget.max_calls,
            "max_duration_seconds": budget.max_duration_seconds,
        }

    mission_id = payload.mission_id or f"msn_{ctx.organisation_id}_001"
    orchestrator = get_orchestrator()

    state = orchestrator.create_run(
        mission_id=mission_id,
        org_id=ctx.organisation_id,
        query=clean_query,
        trace_id=trace_id,
        aoi=payload.aoi,
        metadata={"budget": budget_dict} if budget_dict else None,
    )

    _dispatch_run(state.job_id)

    response_data = ExecuteResponse(
        job_id=state.job_id or "job_unknown",
        mission_id=state.mission_id,
        status="ACCEPTED",
        message="Agent workflow initiated asynchronously",
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=response_data.model_dump(),
        headers={"X-Job-Id": state.job_id or ""},
    )


@router.get("/runs/{job_id}", response_model=MissionState)
async def get_run_status(
    job_id: str,
    ctx: AuthContext = Depends(get_current_user),
    _: AuthContext = Depends(require_role(Role.ANALYST)),
) -> MissionState:
    orchestrator = get_orchestrator()
    run = orchestrator.get_run(job_id)
    if not run or run.organization_id != ctx.organisation_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RUN_NOT_FOUND",
                "message": f"Run with job_id '{job_id}' not found",
                "retryable": False,
            },
        )
    return run
