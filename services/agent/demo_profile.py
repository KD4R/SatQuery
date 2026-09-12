"""
services/agent/demo_profile.py — Runner for the pinned flagship flood demo mission.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from evidence.graph_builder import EvidenceGraphBuilder
from packages.contracts.agent import ConfidenceResponse, MissionState

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
    Executes the pinned flagship flood demo workflow, returning a fully populated,
    deterministic MissionState with evidence graph and grounded explanations.
    """
    profile = load_pinned_demo_profile()

    mission_id = f"msn_{org_id}_{profile['profile_id']}"
    run_id = f"run_demo_{uuid.uuid4().hex[:6]}"
    job_id = f"job_demo_{uuid.uuid4().hex[:8]}"

    # Build Evidence Graph
    builder = EvidenceGraphBuilder(mission_id=mission_id)

    # 1. Observation nodes
    obs_nodes = []
    for obs in profile["observations"]:
        n = builder.add_observation(obs)
        obs_nodes.append(n)

    # 2. Preprocessing node
    prep_node = builder.add_preprocessing(
        obs_node_id=obs_nodes[0].node_id,
        op_name="radiometric_calibration_and_speckle_filter",
        params={"method": "refined_lee", "filter_size": 7},
    )

    # 3. Inference node
    inf_meta = profile["inferences"]
    inf_node = builder.add_inference(
        input_node_ids=[prep_node.node_id],
        model_name=inf_meta["model_name"],
        model_version=inf_meta["model_version"],
        results={
            "inundated_sqkm": inf_meta["inundation_area_sqkm"],
            "structures_impacted": inf_meta["affected_structures_count"],
        },
        confidence=inf_meta["confidence_score"],
    )

    # 4. Metric nodes
    builder.add_metric(
        inference_node_id=inf_node.node_id,
        metric_name="inundation_area_sqkm",
        value=inf_meta["inundation_area_sqkm"],
        unit="km2",
    )
    builder.add_metric(
        inference_node_id=inf_node.node_id,
        metric_name="affected_structures_count",
        value=inf_meta["affected_structures_count"],
        unit="structures",
    )

    evidence_graph = builder.build()

    state = MissionState(
        mission_id=mission_id,
        run_id=run_id,
        job_id=job_id,
        organization_id=org_id,
        trace_id="tr-pinned-demo-assam-001",
        query=profile["query"],
        sanitized_query=profile["query"],
        status="COMPLETED",
        intent={
            "disaster_type": profile["disaster_type"],
            "objectives": ["delineate_hazard_extent", "infrastructure_impact_assessment"],
        },
        aoi=profile["aoi"],
        temporal_window=profile["temporal_window"],
        selected_sensors=profile["selected_sensors"],
        observation_ids=[obs["asset_id"] for obs in profile["observations"]],
        evidence_graph=evidence_graph.model_dump(),
        confidence_score=inf_meta["confidence_score"],
        synthesized_output={
            "summary": (
                f"Assam flood inundation delineated at {inf_meta['inundation_area_sqkm']} sq km "
                f"with {inf_meta['affected_structures_count']} affected structures identified."
            ),
            "metrics": {
                "inundation_area_sqkm": inf_meta["inundation_area_sqkm"],
                "affected_structures_count": inf_meta["affected_structures_count"],
            },
            "why_explanation": profile["why_explanation"],
        },
        metadata={
            "dataset_id": "bhoonidhi-sentinel-1-grd",
            "model_version": inf_meta["model_version"],
            "processing_version": "1.0",
        },
    )
    return state


def run_pinned_demo_profile(
    fixture_path: Optional[str] = None, org_id: str = "org-isro"
) -> Dict[str, Any]:
    """
    Executes the pinned demo profile and returns a structured dictionary summary
    conforming to service integration expectations.
    """
    profile = load_pinned_demo_profile(path=fixture_path)
    state = run_pinned_demo_mission(org_id=org_id)

    inf_meta = profile["inferences"]
    conf_score = float(inf_meta["confidence_score"])
    passed = conf_score >= 0.70

    conf_resp = ConfidenceResponse(
        confidence_score=conf_score,
        passed_gate=passed,
        uncertainty_factors=[],
        action="PROCEED" if passed else "TRIGGER_ALTERNATIVE_SENSOR_ACQUISITION",
        trace_id="tr-pinned-demo-assam-001",
    )

    summary_text = (
        f"Assam flood inundation delineated at {inf_meta['inundation_area_sqkm']} sq km "
        f"with {inf_meta['affected_structures_count']} affected structures identified."
    )

    return {
        "mission_id": "mission-pinned-flood-2026",
        "trace_id": "tr-pinned-demo-assam-001",
        "status": "COMPLETED",
        "synthesis": summary_text,
        "confidence": {
            "confidence_score": conf_score,
            "overall_score": conf_score,
            "passed_gate": passed,
            "uncertainty_factors": [],
            "action": conf_resp.action,
            "decision": conf_resp.action,
            "trace_id": conf_resp.trace_id,
        },
        "evidence_nodes": state.evidence_graph.get("nodes", []) if state.evidence_graph else [],
        "selected_sensors": profile["selected_sensors"],
        "aoi": profile["aoi"],
        "state": state,
    }
