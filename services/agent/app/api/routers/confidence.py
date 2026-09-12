"""
services/agent/app/api/routers/confidence.py — Confidence & uncertainty gate router (P2-11).
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request
from nodes.confidence_gate import evaluate_confidence_gate
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

    return evaluate_confidence_gate(
        evidence_nodes=payload.evidence_nodes,
        sensor_type=payload.sensor_type,
        cloud_cover=payload.cloud_cover,
        resolution_meters=payload.resolution_meters,
        trace_id=trace_id,
    )
