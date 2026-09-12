"""
tests/contracts/test_p2_06_schema_compatibility.py
Contract compatibility tests for P2-06: ToolBudget schema.
"""

import pytest
from services.agent.security.tool_budget import ToolBudget


@pytest.mark.contract
def test_p2_06_schema_compatibility():
    """ToolBudget schema conforms to execution budget contracts."""
    schema = ToolBudget.model_json_schema()
    expected = {"max_calls", "max_duration_seconds", "calls_made", "total_duration_ms"}
    assert expected.issubset(schema["properties"].keys())

    budget = ToolBudget(max_calls=5, max_duration_seconds=30.0)
    data = budget.model_dump()
    assert data["max_calls"] == 5
    assert data["max_duration_seconds"] == 30.0
    assert data["calls_made"] == 0
