"""
tests/unit/test_p2_12_disagreement.py
Unit tests for P2-12: Sensor disagreement analysis.
"""

import pytest
from evidence.disagreement import analyze_sensor_disagreement


@pytest.mark.unit
def test_sensor_disagreement_analysis_valid():
    """Calculates IoU, detects radar shadows, and arbitrates flood area."""
    # 1. Normal sensor agreement
    rep = analyze_sensor_disagreement(
        sar_area_sqkm=150.0,
        optical_area_sqkm=140.0,
        intersection_sqkm=130.0,
    )
    assert rep.iou_score > 0.80
    assert rep.disagreement_percentage < 25.0
    assert rep.likely_anomaly is None
    assert rep.arbitrated_water_area_sqkm == 145.0

    # 2. Steep slope terrain radar shadow anomaly
    rep_shadow = analyze_sensor_disagreement(
        sar_area_sqkm=200.0,  # Radar shadow misclassified as water
        optical_area_sqkm=120.0,
        intersection_sqkm=110.0,
        terrain_slope_deg=22.0,
    )
    assert rep_shadow.likely_anomaly == "RADAR_SHADOW_TERRAIN_ARTEFACT"
    assert rep_shadow.arbitrated_water_area_sqkm == 120.0  # Optical preferred


@pytest.mark.unit
def test_sensor_disagreement_analysis_invalid_input():
    """Negative areas and invalid intersection bounds raise ValueError."""
    with pytest.raises(ValueError, match="Area values must be non-negative"):
        analyze_sensor_disagreement(-10.0, 50.0, 20.0)

    with pytest.raises(ValueError, match="Intersection .* cannot exceed"):
        analyze_sensor_disagreement(100.0, 80.0, 95.0)  # 95 > min(100, 80)
