"""
services/agent/app/api/routers/confidence.py — Confidence & uncertainty gate router.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request
from packages.auth.dependencies import get_current_user, require_role
from packages.auth.models import AuthContext, Role
from packages.contracts.agent import ConfidenceRequest, ConfidenceResponse

router = APIRouter(prefix="/api/v1/agent", tags=["agent-confidence"])


@router.post("/confidence", response_model=ConfidenceResponse)
async def evaluate_confidence(
    payload: ConfidenceRequest,
    request: Request,
    ctx: AuthContext = Depends(get_current_user),
    _: AuthContext = Depends(require_role(Role.ANALYST)),
) -> ConfidenceResponse:
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")

    # Baseline scoring logic
    score = 0.85
    factors = []

    if payload.sensor_type == "OPTICAL" and payload.cloud_cover > 20.0:
        score -= 0.35
        factors.append(f"Optical cloud cover penalty ({payload.cloud_cover}%)")

    if payload.resolution_meters > 20.0:
        score -= 0.15
        factors.append(f"Coarse spatial resolution ({payload.resolution_meters}m)")

    passed = score >= 0.70
    action = "PROCEED" if passed else "TRIGGER_ALTERNATIVE_SENSOR_ACQUISITION"

    return ConfidenceResponse(
        confidence_score=max(0.0, min(1.0, round(score, 2))),
        passed_gate=passed,
        uncertainty_factors=factors,
        action=action,
        trace_id=trace_id,
    )
