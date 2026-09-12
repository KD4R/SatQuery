"""
tests/unit/test_p2_09_sensor_arbitration.py
Unit tests for P2-09: Adaptive sensor arbitration.
"""

import pytest
from nodes.sensor_arbitrator import arbitrate_sensors


@pytest.mark.unit
def test_adaptive_sensor_arbitration_valid():
    """Sensor arbitration selects SAR for clouds/night and Optical for clear daylight."""
    # High clouds -> SAR primary
    cloudy_dec = arbitrate_sensors(hazard_type="flood", cloud_cover=45.0, is_night=False)
    assert cloudy_dec.primary_sensor == "SAR"
    assert cloudy_dec.arbitration_score >= 0.90
    assert "microwave" in cloudy_dec.rationale

    # Nighttime -> SAR primary
    night_dec = arbitrate_sensors(hazard_type="flood", cloud_cover=5.0, is_night=True)
    assert night_dec.primary_sensor == "SAR"
    assert night_dec.secondary_sensor is None

    # Clear daylight -> Optical primary
    clear_dec = arbitrate_sensors(hazard_type="flood", cloud_cover=10.0, is_night=False)
    assert clear_dec.primary_sensor == "OPTICAL"
    assert clear_dec.secondary_sensor == "SAR"


@pytest.mark.unit
def test_adaptive_sensor_arbitration_invalid_input():
    """Invalid cloud cover ranges and empty hazard types raise ValueError."""
    with pytest.raises(ValueError, match="Cloud cover"):
        arbitrate_sensors(cloud_cover=-5.0)

    with pytest.raises(ValueError, match="Cloud cover"):
        arbitrate_sensors(cloud_cover=120.0)

    with pytest.raises(ValueError, match="Hazard type cannot be empty"):
        arbitrate_sensors(hazard_type="")
