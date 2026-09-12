"""
tests/contracts/test_p2_16_schema_compatibility.py
Contract compatibility tests for P2-16: ToolAuditEntry schema.
"""

import pytest
from security.audit import ToolAuditEntry


@pytest.mark.contract
def test_p2_16_schema_compatibility():
    """ToolAuditEntry schema conforms to audit contract."""
    schema = ToolAuditEntry.model_json_schema()
    expected = {
        "audit_id",
        "tool_name",
        "caller",
        "organization_id",
        "sanitized_args",
        "status",
        "execution_time_ms",
        "trace_id",
        "timestamp",
    }
    assert expected.issubset(schema["properties"].keys())
