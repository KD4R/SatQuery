"""
tests/unit/test_p2_16_observability.py
Unit tests for P2-16: Agent observability and tool-call audit.
"""

import pytest
from packages.observability.agent_metrics import AgentMetrics
from services.agent.security.audit import AuditLogger


@pytest.mark.unit
def test_agent_observability_and_tool_call_audit_valid():
    """AgentMetrics snapshots and AuditLogger secret redaction function correctly."""
    # 1. Metrics recording
    metrics = AgentMetrics()
    metrics.record_node_duration("planning", 45.2)
    metrics.record_node_duration("planning", 52.8)
    metrics.record_tool_call("stac_search", "success")
    metrics.record_confidence_gate(passed=True, action="PROCEED")
    metrics.record_prompt_injection_block()

    snap = metrics.get_snapshot()
    assert snap["agent_node_duration_ms"]["planning"]["count"] == 2
    assert snap["agent_node_duration_ms"]["planning"]["avg_ms"] == 49.0
    assert snap["agent_tool_calls_total"]["stac_search:success"] == 1
    assert snap["confidence_gate_total"]["passed"] == 1
    assert snap["prompt_injection_block_total"] == 1

    # 2. Audit logging with secret redaction
    logger = AuditLogger()
    entry = logger.log_tool_call(
        tool_name="stac_search",
        args={
            "bbox": [92.0, 26.0, 93.0, 27.0],
            "api_key": "secret-12345",
            "auth_token": "bearer-xyz",
        },
        caller="user:analyst-1",
        org_id="org-isro",
        status="success",
        execution_time_ms=15.4,
        trace_id="tr-audit-001",
    )
    assert entry.sanitized_args["api_key"] == "[REDACTED]"
    assert entry.sanitized_args["auth_token"] == "[REDACTED]"
    assert entry.sanitized_args["bbox"] == [92.0, 26.0, 93.0, 27.0]
    assert len(logger.get_entries("org-isro")) == 1


@pytest.mark.unit
def test_agent_observability_and_tool_call_audit_invalid_input():
    """Invalid metric durations and empty audit logger fields raise ValueError."""
    metrics = AgentMetrics()
    with pytest.raises(ValueError, match="Node name cannot be empty"):
        metrics.record_node_duration("", 10.0)

    with pytest.raises(ValueError, match="Duration cannot be negative"):
        metrics.record_node_duration("planning", -5.0)

    logger = AuditLogger()
    with pytest.raises(ValueError, match="tool_name cannot be empty"):
        logger.log_tool_call(
            tool_name="",
            args={},
            caller="user",
            org_id="org",
            status="ok",
            execution_time_ms=1.0,
        )

    with pytest.raises(ValueError, match="org_id cannot be empty"):
        logger.log_tool_call(
            tool_name="stac_search",
            args={},
            caller="user",
            org_id="",
            status="ok",
            execution_time_ms=1.0,
        )
