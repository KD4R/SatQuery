"""
services/agent/app/api/routers/plan.py — Mission planning router.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request
from packages.auth.dependencies import get_current_user, require_role
from packages.auth.models import AuthContext, Role
from packages.contracts.agent import PlanRequest, PlanResponse, PlanStep
from security.sanitizer import sanitize_prompt
from security.validator import validate_aoi_geometry

router = APIRouter(prefix="/api/v1/agent", tags=["agent-plan"])


@router.post("/plan", response_model=PlanResponse)
async def create_plan(
    payload: PlanRequest,
    request: Request,
    ctx: AuthContext = Depends(get_current_user),
    _: AuthContext = Depends(require_role(Role.ANALYST)),
) -> PlanResponse:
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")
    sanitized_query = sanitize_prompt(payload.query)
    if payload.aoi:
        validate_aoi_geometry(payload.aoi)

    mission_id = payload.mission_id or f"msn_{ctx.organisation_id}_001"

    # Default deterministic initial plan for flood assessment
    steps = [
        PlanStep(
            step_id="step-1",
            name="search_observations",
            description="Query Bhoonidhi/STAC for SAR and Optical scenes",
            tool="stac_search",
        ),
        PlanStep(
            step_id="step-2",
            name="sensor_arbitration",
            description="Select optimal sensor based on cloud cover and day/night state",
            tool="sensor_arbitrator",
        ),
        PlanStep(
            step_id="step-3",
            name="build_evidence",
            description="Aggregate observation metadata into Evidence Graph",
            tool="evidence_builder",
        ),
        PlanStep(
            step_id="step-4",
            name="confidence_gate",
            description="Evaluate composite uncertainty gate",
            tool="confidence_evaluator",
        ),
    ]

    return PlanResponse(
        mission_id=mission_id,
        intent={
            "disaster_type": "flood",
            "target": "inundation_assessment",
            "raw_query": payload.query,
            "sanitized_query": sanitized_query,
        },
        plan_steps=steps,
        selected_sensors=["S1_SAR", "S2_OPTICAL"],
        trace_id=trace_id,
    )
