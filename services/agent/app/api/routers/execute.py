"""
services/agent/app/api/routers/execute.py — Async agent execute router.
"""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from packages.auth.dependencies import get_current_user, require_role
from packages.auth.models import AuthContext, Role
from packages.contracts.agent import ExecuteRequest, ExecuteResponse

router = APIRouter(prefix="/api/v1/agent", tags=["agent-execute"])


@router.post("/execute", status_code=status.HTTP_202_ACCEPTED, response_model=ExecuteResponse)
async def execute_agent(
    payload: ExecuteRequest,
    request: Request,
    ctx: AuthContext = Depends(get_current_user),
    _: AuthContext = Depends(require_role(Role.ANALYST)),
):
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    mission_id = payload.mission_id or f"msn_{ctx.organisation_id}_{uuid.uuid4().hex[:8]}"

    response_data = ExecuteResponse(
        job_id=job_id,
        mission_id=mission_id,
        status="ACCEPTED",
        message="Agent workflow initiated asynchronously",
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=response_data.model_dump(),
        headers={"X-Job-Id": job_id},
    )
