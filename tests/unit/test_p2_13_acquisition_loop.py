"""
tests/unit/test_p2_13_acquisition_loop.py
Unit tests for P2-13: Autonomous evidence acquisition loop.
"""

import pytest
from services.agent.graph.acquisition_loop import AutonomousAcquisitionLoop
from packages.contracts.agent import MissionState


@pytest.mark.unit
def test_autonomous_evidence_acquisition_loop_valid():
    """Acquisition loop acquires complementary SAR scenes to resolve uncertainty."""
    state = MissionState(
        mission_id="msn-loop-001",
        run_id="run-001",
        organization_id="org-isro",
        query="Map flood under severe cloud cover",
        selected_sensors=["S2_OPTICAL"],  # Starts with cloud-occluded optical
    )

    loop = AutonomousAcquisitionLoop()
    updated_state, result = loop.run_loop(
        state=state,
        max_iterations=3,
        target_confidence=0.70,
    )

    assert result.resolved is True
    assert result.iterations_run >= 1
    assert result.final_confidence >= 0.70
    assert "S1_SAR" in updated_state.selected_sensors
    assert any("ACQ" in obs for obs in result.acquired_observations)
    assert updated_state.status == "COMPLETED"


@pytest.mark.unit
def test_autonomous_evidence_acquisition_loop_invalid_input():
    """Zero max_iterations or out-of-bounds target confidence raises ValueError."""
    state = MissionState(
        mission_id="msn-001",
        run_id="run-001",
        organization_id="org-isro",
        query="Flood analysis",
    )
    loop = AutonomousAcquisitionLoop()

    with pytest.raises(ValueError, match="max_iterations must be strictly positive"):
        loop.run_loop(state, max_iterations=0)

    with pytest.raises(ValueError, match="target_confidence must be in range"):
        loop.run_loop(state, target_confidence=1.5)
