"""
nodes/confidence_gate.py — Confidence evaluation and uncertainty gating node.
"""

from typing import Any, Dict, List, Optional
from packages.contracts.agent import ConfidenceResponse


def evaluate_confidence_gate(
    evidence_nodes: Optional[List[Dict[str, Any]]] = None,
    sensor_type: str = "SAR",
    cloud_cover: float = 0.0,
    resolution_meters: float = 10.0,
    temporal_lag_days: float = 0.0,
    trace_id: Optional[str] = None,
) -> ConfidenceResponse:
    """
    Evaluates evidence against multi-factor confidence criteria:
    sensor physics, cloud interference, spatial resolution, and temporal baseline lag.
    """
    if not (0.0 <= cloud_cover <= 100.0):
        raise ValueError(f"Cloud cover {cloud_cover}% must be between 0.0 and 100.0")

    if resolution_meters <= 0.0:
        raise ValueError("Spatial resolution must be strictly positive")

    if temporal_lag_days < 0.0:
        raise ValueError("Temporal lag days cannot be negative")

    # Composite baseline confidence
    score = 0.95
    uncertainty_factors: List[str] = []

    # 1. Optical cloud contamination penalty
    if "OPTICAL" in sensor_type.upper() and cloud_cover > 15.0:
        penalty = min(0.40, (cloud_cover - 15.0) * 0.015)
        score -= penalty
        uncertainty_factors.append(
            f"Optical imagery partially occluded by {cloud_cover:.1f}% cloud cover (-{penalty:.2f})"
        )

    # 2. Coarse spatial resolution penalty
    if resolution_meters > 20.0:
        penalty = min(0.30, (resolution_meters - 20.0) * 0.01)
        score -= penalty
        uncertainty_factors.append(
            f"Coarse spatial resolution ({resolution_meters:.1f}m) "
            f"exceeds 20m threshold (-{penalty:.2f})"
        )

    # 3. Temporal lag penalty
    if temporal_lag_days > 14.0:
        penalty = min(0.25, (temporal_lag_days - 14.0) * 0.01)
        score -= penalty
        uncertainty_factors.append(
            f"Temporal baseline lag ({temporal_lag_days:.1f} days) exceeds 14 days (-{penalty:.2f})"
        )

    # 4. Check if inference nodes exist and incorporate their model confidence
    if evidence_nodes:
        inf_nodes = [n for n in evidence_nodes if n.get("node_type") == "INFERENCE"]
        if inf_nodes:
            avg_inf_conf = sum(n.get("confidence", 0.85) for n in inf_nodes) / len(inf_nodes)
            score = (score + avg_inf_conf) / 2.0

    final_score = max(0.0, min(1.0, round(score, 2)))
    passed = final_score >= 0.70

    action = "PROCEED" if passed else "TRIGGER_ALTERNATIVE_SENSOR_ACQUISITION"

    return ConfidenceResponse(
        confidence_score=final_score,
        passed_gate=passed,
        uncertainty_factors=uncertainty_factors,
        action=action,
        trace_id=trace_id,
    )
