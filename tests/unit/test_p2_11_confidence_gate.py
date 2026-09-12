"""
tests/unit/test_p2_11_confidence_gate.py
Unit tests for P2-11: Confidence and uncertainty gate.
"""

import pytest
from nodes.confidence_gate import evaluate_confidence_gate


@pytest.mark.unit
def test_confidence_and_uncertainty_gate_valid():
    """High quality evidence passes gate; heavily degraded input triggers acquisition."""
    # High-quality SAR evidence passes
    high_qual = evaluate_confidence_gate(
        sensor_type="SAR",
        cloud_cover=0.0,
        resolution_meters=10.0,
        temporal_lag_days=2.0,
    )
    assert high_qual.passed_gate is True
    assert high_qual.confidence_score >= 0.70
    assert high_qual.action == "PROCEED"
    assert len(high_qual.uncertainty_factors) == 0

    # Heavily cloud-occluded Optical imagery fails gate
    occluded_opt = evaluate_confidence_gate(
        sensor_type="OPTICAL",
        cloud_cover=65.0,
        resolution_meters=10.0,
        temporal_lag_days=18.0,
    )
    assert occluded_opt.passed_gate is False
    assert occluded_opt.action == "TRIGGER_ALTERNATIVE_SENSOR_ACQUISITION"
    assert len(occluded_opt.uncertainty_factors) >= 2


@pytest.mark.unit
def test_confidence_and_uncertainty_gate_invalid_input():
    """Invalid cloud cover, negative resolution, or negative lag raise ValueError."""
    with pytest.raises(ValueError, match="Cloud cover"):
        evaluate_confidence_gate(cloud_cover=-5.0)

    with pytest.raises(ValueError, match="strictly positive"):
        evaluate_confidence_gate(resolution_meters=0.0)

    with pytest.raises(ValueError, match="Temporal lag days cannot be negative"):
        evaluate_confidence_gate(temporal_lag_days=-1.0)
