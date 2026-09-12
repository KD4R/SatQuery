"""
services/agent/app/api/routers/sensor_decision.py — Adaptive sensor decision router (P2-09).
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request
from services.agent.nodes.sensor_arbitrator import arbitrate_sensors
from packages.auth.dependencies import get_current_user, require_role
from packages.auth.models import AuthContext, Role
from services.agent.schemas import SensorDecisionRequest, SensorDecisionResponse

router = APIRouter(prefix="/api/v1/agent", tags=["agent-sensor-decision"])


@router.post("/sensor-decision", response_model=SensorDecisionResponse)
async def sensor_decision(
    payload: SensorDecisionRequest,
    request: Request,
    ctx: AuthContext = Depends(get_current_user),
    _: AuthContext = Depends(require_role(Role.ANALYST)),
) -> SensorDecisionResponse:
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")

    return arbitrate_sensors(
        hazard_type=payload.hazard_type,
        cloud_cover=payload.cloud_cover_percentage,
        is_night=payload.is_night,
        priority=payload.priority,
        trace_id=trace_id,
    )
