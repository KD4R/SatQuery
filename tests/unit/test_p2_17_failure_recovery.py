"""
tests/unit/test_p2_17_failure_recovery.py
Unit tests for P2-17: Agent failure/recovery policies.
"""

import pytest
from services.agent.nodes.resilience import execute_with_recovery


@pytest.mark.unit
def test_agent_failure_recovery_policies_valid():
    """
    Operations succeed normally or fall back to permitted backup fixtures
    upon upstream failure.
    """
    # 1. Healthy execution
    healthy = execute_with_recovery(
        action_name="bhoonidhi_search",
        primary_fn=lambda: {"scenes": ["S1_SCENE_1"]},
        fallback_fn=lambda: {"scenes": ["PINNED_DEMO_SCENE"]},
    )
    assert healthy.success is True
    assert healthy.used_fallback is False
    assert healthy.status == "HEALTHY"
    assert healthy.retries_attempted == 0

    # 2. Failing upstream triggers retries and falls back
    def _fail():
        raise TimeoutError("Upstream Bhoonidhi gateway timed out (504)")

    recovered = execute_with_recovery(
        action_name="bhoonidhi_search",
        primary_fn=_fail,
        fallback_fn=lambda: {"scenes": ["PINNED_DEMO_SCENE"], "fixture_type": "pinned_backup"},
        max_retries=2,
    )
    assert recovered.success is True
    assert recovered.used_fallback is True
    assert recovered.status == "DEGRADED_FALLBACK"
    assert recovered.retries_attempted == 2
    assert "PINNED_DEMO_SCENE" in recovered.data["scenes"]
    assert "failed after 2 retries" in (recovered.warning or "")


@pytest.mark.unit
def test_agent_failure_recovery_policies_invalid_input():
    """Negative retries and empty action names raise ValueError."""
    with pytest.raises(ValueError, match="max_retries cannot be negative"):
        execute_with_recovery(
            action_name="op",
            primary_fn=lambda: True,
            fallback_fn=lambda: False,
            max_retries=-1,
        )

    with pytest.raises(ValueError, match="action_name cannot be empty"):
        execute_with_recovery(
            action_name="",
            primary_fn=lambda: True,
            fallback_fn=lambda: False,
        )
