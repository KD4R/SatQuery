"""
tests/contracts/test_p2_08_schema_compatibility.py
Contract compatibility tests for P2-08: TemporalPlan and TemporalWindow.
"""

import pytest
from services.agent.nodes.temporal_planner import TemporalPlan, TemporalWindow


@pytest.mark.contract
def test_p2_08_schema_compatibility():
    """TemporalPlan and TemporalWindow schemas conform to contract requirements."""
    plan_schema = TemporalPlan.model_json_schema()
    expected_plan = {
        "event_date",
        "baseline_window",
        "crisis_window",
        "sensor_match_strategy",
        "recommended_pairing",
    }
    assert expected_plan.issubset(plan_schema["properties"].keys())

    window_schema = TemporalWindow.model_json_schema()
    expected_window = {"start_date", "end_date", "label"}
    assert expected_window.issubset(window_schema["properties"].keys())
