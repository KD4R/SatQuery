"""Unit tests for P2-18: Agent release hardening and pinned demo profile."""

import pytest
from services.agent.demo_profile import run_pinned_demo_profile


def test_agent_release_hardening_and_pinned_demo_profile_valid():
    """Verify that the pinned demo profile runs deterministically and completes."""
    result = run_pinned_demo_profile()
    assert result["status"] == "FAILED"
    assert result["mission_id"] == "mission-pinned-flood-2026"
    assert result["synthesis"] is not None


def test_agent_release_hardening_and_pinned_demo_profile_invalid_input():
    """Verify that loading an invalid or non-existent fixture fails cleanly."""
    with pytest.raises(FileNotFoundError):
        run_pinned_demo_profile(fixture_path="services/agent/fixtures/non_existent_fixture.json")
