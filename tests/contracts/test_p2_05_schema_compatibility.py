"""
tests/contracts/test_p2_05_schema_compatibility.py
Contract compatibility tests for P2-05: ToolResult and schema contracts.
"""

import pytest
from tools.base import ToolResult


@pytest.mark.contract
def test_p2_05_schema_compatibility():
    """ToolResult schema conforms to execution contract."""
    schema = ToolResult.model_json_schema()
    expected = {"success", "output", "error", "execution_time_ms", "metadata"}
    assert expected.issubset(schema["properties"].keys())

    res = ToolResult(success=True, output={"scenes": 4}, execution_time_ms=12.5)
    data = res.model_dump()
    assert data["success"] is True
    assert data["output"]["scenes"] == 4
    assert data["execution_time_ms"] == 12.5
