"""
services/agent/demo_profile.py — Runner for the pinned flagship flood demo mission.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from services.agent.schemas import ConfidenceResponse, MissionState
from services.agent.graph.orchestrator import get_orchestrator

_DEFAULT_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pinned_flood_mission.json"


def load_pinned_demo_profile(path: Optional[str] = None) -> Dict[str, Any]:
    """Loads the deterministic pinned demo mission profile from fixture file."""
    fixture_path = Path(path) if path else _DEFAULT_FIXTURE_PATH
    if not fixture_path.exists():
        raise FileNotFoundError(f"Pinned demo fixture not found at {fixture_path}")

    with open(fixture_path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
        return data


def run_pinned_demo_mission(org_id: str = "org-isro") -> MissionState:
    """
    Executes the pinned flagship flood demo workflow via the real agent orchestrator.
    """
    profile = load_pinned_demo_profile()

    mission_id = "mission-pinned-flood-2026"

    orch = get_orchestrator()
    state = orch.create_run(
        mission_id=mission_id,
        org_id=org_id,
        query=profile["query"],
        trace_id="tr-pinned-demo-assam-001",
        aoi=profile["aoi"],
        metadata={"fixture_type": "pinned_backup"},  # Instructs nodes to use fallback if needed
    )

    # Use real graph execution instead of manually fabricating state
    completed_state = orch.step_execution(state)
    return completed_state


def run_pinned_demo_profile(
    fixture_path: Optional[str] = None, org_id: str = "org-isro"
) -> Dict[str, Any]:
    """
    Executes the pinned demo profile and returns a structured dictionary summary
    conforming to service integration expectations.
    """
    profile = load_pinned_demo_profile(path=fixture_path)
    state = run_pinned_demo_mission(org_id=org_id)

    return {
        "mission_id": "mission-pinned-flood-2026",
        "trace_id": state.trace_id,
        "status": state.status,
        "synthesis": state.synthesized_output.get("summary", ""),
        "confidence": {
            "confidence_score": state.confidence_score,
            "overall_score": state.confidence_score,
            "passed_gate": state.confidence_score >= 0.70,
            "uncertainty_factors": [],
            "action": (
                "PROCEED"
                if state.confidence_score >= 0.70
                else "TRIGGER_ALTERNATIVE_SENSOR_ACQUISITION"
            ),
            "decision": (
                "PROCEED"
                if state.confidence_score >= 0.70
                else "TRIGGER_ALTERNATIVE_SENSOR_ACQUISITION"
            ),
            "trace_id": state.trace_id,
        },
        "evidence_nodes": state.evidence_graph.get("nodes", []) if state.evidence_graph else [],
        "selected_sensors": state.selected_sensors,
        "aoi": state.aoi,
        "state": state,
    }
