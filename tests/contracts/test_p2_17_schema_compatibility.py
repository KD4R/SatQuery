"""
tests/contracts/test_p2_17_schema_compatibility.py
Contract compatibility tests for P2-17: RecoveryResult schema.
"""

import pytest
from services.agent.nodes.resilience import RecoveryResult


@pytest.mark.contract
def test_p2_17_schema_compatibility():
    """RecoveryResult schema conforms to reliability contract."""
    schema = RecoveryResult.model_json_schema()
    expected = {"success", "used_fallback", "retries_attempted", "data", "status", "warning"}
    assert expected.issubset(schema["properties"].keys())
