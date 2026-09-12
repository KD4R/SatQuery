"""
services/agent/app/api/routers/sensor_decision.py — Adaptive sensor decision router.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request
from packages.auth.dependencies import get_current_user, require_role
from packages.auth.models import AuthContext, Role
from packages.contracts.agent import SensorDecisionRequest, SensorDecisionResponse

router = APIRouter(prefix="/api/v1/agent", tags=["agent-sensor-decision"])


@router.post("/sensor-decision", response_model=SensorDecisionResponse)
async def sensor_decision(
    payload: SensorDecisionRequest,
    request: Request,
    ctx: AuthContext = Depends(get_current_user),
    _: AuthContext = Depends(require_role(Role.ANALYST)),
) -> SensorDecisionResponse:
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")

    # Deterministic sensor arbitration rule:
    # If cloud cover > 20% or night -> SAR is mandatory for all-weather penetration
    if payload.cloud_cover_percentage > 20.0 or payload.is_night:
        primary = "SAR"
        secondary = "OPTICAL" if not payload.is_night else None
        rationale = (
            f"High cloud cover ({payload.cloud_cover_percentage}%) or night ({payload.is_night}) "
            "requires SAR active microwave imaging to penetrate atmospheric occlusion."
        )
        score = 0.95
    else:
        primary = "OPTICAL"
        secondary = "SAR"
        rationale = (
            f"Low cloud cover ({payload.cloud_cover_percentage}%) enables multispectral Optical "
            "imagery with high spatial resolution and water index calculation."
        )
        score = 0.90

    return SensorDecisionResponse(
        primary_sensor=primary,
        secondary_sensor=secondary,
        rationale=rationale,
        arbitration_score=score,
        trace_id=trace_id,
    )
