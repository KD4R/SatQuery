"""
tests/contracts/test_p2_01_schema_compatibility.py
Contract compatibility tests for P2-01: MissionState schema.
"""

import pytest
from services.agent.schemas import (
    ConfidenceRequest,
    ConfidenceResponse,
    ExecuteRequest,
    ExecuteResponse,
    MissionState,
    PlanRequest,
    PlanResponse,
    SensorDecisionRequest,
    SensorDecisionResponse,
)


@pytest.mark.contract
def test_p2_01_schema_compatibility():
    """MissionState and Agent DTO schemas have all required canonical fields."""
    state_schema = MissionState.model_json_schema()
    expected_state_fields = {
        "mission_id",
        "run_id",
        "organization_id",
        "query",
        "status",
        "confidence_score",
        "metadata",
        "created_at",
        "updated_at",
    }
    assert expected_state_fields.issubset(state_schema["properties"].keys())

    # Verify DTO schemas
    assert {"query"}.issubset(PlanRequest.model_json_schema()["properties"].keys())
    assert {"mission_id", "plan_steps"}.issubset(
        PlanResponse.model_json_schema()["properties"].keys()
    )
    assert {"query"}.issubset(ExecuteRequest.model_json_schema()["properties"].keys())
    assert {"job_id", "status"}.issubset(ExecuteResponse.model_json_schema()["properties"].keys())
    assert {"hazard_type"}.issubset(SensorDecisionRequest.model_json_schema()["properties"].keys())
    assert {"primary_sensor", "arbitration_score"}.issubset(
        SensorDecisionResponse.model_json_schema()["properties"].keys()
    )
    assert {"sensor_type"}.issubset(ConfidenceRequest.model_json_schema()["properties"].keys())
    assert {"confidence_score", "passed_gate"}.issubset(
        ConfidenceResponse.model_json_schema()["properties"].keys()
    )
