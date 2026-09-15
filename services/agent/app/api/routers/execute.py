"""
services/agent/app/api/routers/execute.py — Async agent execute router (P2-04).
"""

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
from services.agent.worker import process_agent_run

router = APIRouter(prefix="/api/v1/agent", tags=["agent-execute"])


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

    # Trigger orchestrator step execution asynchronously via Celery
    if state.job_id:
        process_agent_run.delay(state.job_id)

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
