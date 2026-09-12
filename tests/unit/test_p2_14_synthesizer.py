"""
tests/unit/test_p2_14_synthesizer.py
Unit tests for P2-14: Evidence-only output synthesizer and WHY explanation.
"""

import pytest
from services.agent.evidence.graph_builder import EvidenceGraphBuilder
from services.agent.evidence.models import EvidenceGraph
from services.agent.nodes.synthesizer import synthesize_evidence_output


@pytest.mark.unit
def test_evidence_only_output_synthesizer_and_why_explanation_valid():
    """Synthesizer produces evidence-only summary, node citations, and WHY explanation."""
    builder = EvidenceGraphBuilder(mission_id="msn-synth-001")
    obs = builder.add_observation(
        {
            "asset_id": "S1A_IW_GRDH_2026",
            "sensor": "S1_SAR",
            "datetime": "2026-09-02T00:35:12Z",
        }
    )
    inf = builder.add_inference(
        input_node_ids=[obs.node_id],
        model_name="water_unet",
        model_version="v2.0",
        results={"flooded_area": 142.5},
        confidence=0.91,
    )
    builder.add_metric(
        inference_node_id=inf.node_id,
        metric_name="inundation_area_sqkm",
        value=142.5,
        unit="km2",
    )
    graph = builder.build()

    out = synthesize_evidence_output(graph, "Explain flood findings")
    assert out.grounding_score == 1.0
    assert len(out.citations) == 3
    assert out.metrics["inundation_area_sqkm"] == 142.5
    assert "why_explanation" in out.model_dump()
    assert "sensor_choice" in out.why_explanation
    assert "Sentinel-1 SAR" in out.why_explanation["sensor_choice"]


@pytest.mark.unit
def test_evidence_only_output_synthesizer_and_why_explanation_invalid_input():
    """Empty EvidenceGraph raises ValueError to prevent hallucination without evidence."""
    empty_graph = EvidenceGraph(graph_id="empty", mission_id="empty")
    with pytest.raises(ValueError, match="Cannot synthesize output from an empty EvidenceGraph"):
        synthesize_evidence_output(empty_graph, "What is the flood status?")
