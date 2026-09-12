"""
tests/contracts/test_p2_09_schema_compatibility.py
Contract compatibility tests for P2-09: SensorDecisionRequest and SensorDecisionResponse.
"""

import pytest
from services.agent.schemas import SensorDecisionRequest, SensorDecisionResponse


@pytest.mark.contract
def test_p2_09_schema_compatibility():
    """Sensor decision request/response schemas conform to contract."""
    req_schema = SensorDecisionRequest.model_json_schema()
    assert {"hazard_type", "cloud_cover_percentage", "is_night", "priority"}.issubset(
        req_schema["properties"].keys()
    )

    resp_schema = SensorDecisionResponse.model_json_schema()
    assert {
        "primary_sensor",
        "secondary_sensor",
        "rationale",
        "arbitration_score",
        "trace_id",
    }.issubset(resp_schema["properties"].keys())
