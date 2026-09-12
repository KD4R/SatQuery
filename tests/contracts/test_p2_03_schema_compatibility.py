"""
tests/contracts/test_p2_03_schema_compatibility.py
Contract compatibility tests for P2-03: PlanRequest, PlanResponse, and PlanStep.
"""

import pytest
from packages.contracts.agent import PlanRequest, PlanResponse, PlanStep


@pytest.mark.contract
def test_p2_03_schema_compatibility():
    """Plan DTO schemas conform strictly to expected fields."""
    req_schema = PlanRequest.model_json_schema()
    assert {"query", "mission_id", "aoi", "metadata"}.issubset(req_schema["properties"].keys())

    resp_schema = PlanResponse.model_json_schema()
    assert {"mission_id", "intent", "plan_steps", "selected_sensors", "trace_id"}.issubset(
        resp_schema["properties"].keys()
    )

    step_schema = PlanStep.model_json_schema()
    assert {"step_id", "name", "description", "tool", "parameters"}.issubset(
        step_schema["properties"].keys()
    )
