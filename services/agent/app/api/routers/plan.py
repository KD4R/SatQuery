"""
services/agent/app/api/routers/plan.py — Mission planning router (P2-03).
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request
from services.agent.nodes.intent_extractor import extract_intent_and_plan
from packages.auth.dependencies import get_current_user, require_role
from packages.auth.models import AuthContext, Role
from packages.contracts.agent import PlanRequest, PlanResponse

router = APIRouter(prefix="/api/v1/agent", tags=["agent-plan"])


@router.post("/plan", response_model=PlanResponse)
async def create_plan(
    payload: PlanRequest,
    request: Request,
    ctx: AuthContext = Depends(get_current_user),
    _: AuthContext = Depends(require_role(Role.ANALYST)),
) -> PlanResponse:
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")
    mission_id = payload.mission_id or f"msn_{ctx.organisation_id}_001"

    intent, plan_steps, selected_sensors = extract_intent_and_plan(
        query=payload.query,
        aoi=payload.aoi,
        metadata=payload.metadata,
    )

    return PlanResponse(
        mission_id=mission_id,
        intent=intent,
        plan_steps=plan_steps,
        selected_sensors=selected_sensors,
        trace_id=trace_id,
    )
