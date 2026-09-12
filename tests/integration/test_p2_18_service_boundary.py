"""Integration tests for P2-18 service boundary."""

from services.agent.demo_profile import run_pinned_demo_profile


def test_p2_18_service_boundary():
    """Verify that release hardening demo profile produces valid end-to-end domain output."""
    output = run_pinned_demo_profile()
    assert output["status"] == "COMPLETED"
    assert "evidence_nodes" in output
    assert "confidence" in output
    assert output["confidence"]["overall_score"] > 0.0
    assert "synthesis" in output
