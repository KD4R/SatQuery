"""Contract tests for P2-18 schema compatibility."""

from graph.state import MissionState
from packages.contracts.agent import ConfidenceResponse
from services.agent.demo_profile import run_pinned_demo_profile


def test_p2_18_schema_compatibility():
    """Verify demo output dictionary is schema compatible with canonical domain types."""
    result = run_pinned_demo_profile()
    conf_report = ConfidenceResponse.model_validate(result["confidence"])
    assert conf_report.action in (
        "PROCEED",
        "CLARIFY",
        "ACQUIRE_MORE",
        "TRIGGER_ALTERNATIVE_SENSOR_ACQUISITION",
    )

    # State schema validation check
    state = MissionState(
        mission_id=result["mission_id"],
        run_id="run-demo-test",
        organization_id="org-isro",
        query="Assess flood inundation extent in Assam",
        trace_id=result["trace_id"],
        status=result["status"],
        confidence_score=result["confidence"]["overall_score"],
    )
    assert state.mission_id == "mission-pinned-flood-2026"
    assert state.status == "COMPLETED"
