"""
tests/unit/test_p2_01_agent_service_skeleton.py
Unit tests for P2-01: Agent service skeleton and MissionState.
"""

import pytest
from pydantic import ValidationError

from packages.contracts.agent import MissionState
from services.agent.app.api.implementation import app


@pytest.mark.unit
def test_agent_service_skeleton_and_missionstate_valid():
    """Valid MissionState creation and FastAPI skeleton metadata."""
    state = MissionState(
        mission_id="msn-assam-001",
        run_id="run-001",
        organization_id="org-isro",
        query="Assess flood inundation in Brahmaputra basin",
        status="INITIALIZED",
        selected_sensors=["S1_SAR", "S2_OPTICAL"],
        metadata={"dataset_id": "bhoonidhi-s1-grd", "model_version": "v1.2.0"},
    )
    assert state.mission_id == "msn-assam-001"
    assert state.organization_id == "org-isro"
    assert state.status == "INITIALIZED"
    assert state.confidence_score == 0.0
    assert "S1_SAR" in state.selected_sensors
    assert state.metadata["model_version"] == "v1.2.0"
    assert app.title == "SatQuery Agent Service"


@pytest.mark.unit
def test_agent_service_skeleton_and_missionstate_invalid_input():
    """MissionState rejects invalid inputs (e.g. empty query or out-of-range confidence)."""
    # Empty query should raise validation error
    with pytest.raises(ValidationError):
        MissionState(
            mission_id="msn-001",
            run_id="run-001",
            organization_id="org-isro",
            query="",  # Empty string rejected by min_length=1
        )

    # Confidence score > 1.0 or < 0.0 should raise validation error
    with pytest.raises(ValidationError):
        MissionState(
            mission_id="msn-001",
            run_id="run-001",
            organization_id="org-isro",
            query="Valid prompt",
            confidence_score=1.5,
        )

    with pytest.raises(ValidationError):
        MissionState(
            mission_id="msn-001",
            run_id="run-001",
            organization_id="org-isro",
            query="Valid prompt",
            confidence_score=-0.1,
        )
