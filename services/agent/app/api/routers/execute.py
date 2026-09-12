"""
services/agent/app/api/routers/execute.py — Async agent execute router (P2-04).
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from services.agent.graph.orchestrator import get_orchestrator
from packages.auth.dependencies import get_current_user, require_role
from packages.auth.models import AuthContext, Role
from packages.contracts.agent import ExecuteRequest, ExecuteResponse, MissionState
from services.agent.security.sanitizer import sanitize_prompt
from services.agent.security.validator import validate_aoi_geometry

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

    mission_id = payload.mission_id or f"msn_{ctx.organisation_id}_001"
    orchestrator = get_orchestrator()

    state = orchestrator.create_run(
        mission_id=mission_id,
        org_id=ctx.organisation_id,
        query=clean_query,
        trace_id=trace_id,
        aoi=payload.aoi,
    )

    # Trigger orchestrator step execution
    orchestrator.step_execution(state)

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
