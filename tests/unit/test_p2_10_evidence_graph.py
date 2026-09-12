"""
tests/unit/test_p2_10_evidence_graph.py
Unit tests for P2-10: Evidence object / graph builder.
"""

import pytest
from evidence.graph_builder import EvidenceGraphBuilder
from evidence.models import EvidenceNodeType


@pytest.mark.unit
def test_evidence_object_graph_builder_valid():
    """EvidenceGraphBuilder correctly links observations, inferences, and metrics."""
    builder = EvidenceGraphBuilder(mission_id="msn-assam-001")

    # 1. Add raw SAR observation
    obs_node = builder.add_observation(
        {
            "asset_id": "S1A_IW_GRDH_1SDV_20260902",
            "sensor": "S1_SAR",
            "datetime": "2026-09-02T00:35:12Z",
        }
    )
    assert obs_node.node_type == EvidenceNodeType.OBSERVATION
    assert obs_node.source == "S1_SAR"

    # 2. Add Preprocessing
    prep_node = builder.add_preprocessing(
        obs_node_id=obs_node.node_id,
        op_name="lee_speckle_filter",
        params={"window_size": 7},
    )
    assert prep_node.node_type == EvidenceNodeType.PREPROCESSING

    # 3. Add Inference
    inf_node = builder.add_inference(
        input_node_ids=[prep_node.node_id],
        model_name="water_segmenter",
        model_version="v2.1",
        results={"water_pixels": 450000},
        confidence=0.92,
    )
    assert inf_node.node_type == EvidenceNodeType.INFERENCE
    assert inf_node.confidence == 0.92

    # 4. Add Metric
    metric_node = builder.add_metric(
        inference_node_id=inf_node.node_id,
        metric_name="inundation_area_sqkm",
        value=142.5,
        unit="km2",
    )
    assert metric_node.node_type == EvidenceNodeType.METRIC

    # 5. Build Graph
    graph = builder.build()
    assert graph.mission_id == "msn-assam-001"
    assert len(graph.nodes) == 4
    assert len(graph.edges) == 3


@pytest.mark.unit
def test_evidence_object_graph_builder_invalid_input():
    """Missing parent nodes, empty IDs, and invalid confidence raise errors."""
    with pytest.raises(ValueError, match="mission_id cannot be empty"):
        EvidenceGraphBuilder(mission_id="")

    builder = EvidenceGraphBuilder(mission_id="msn-001")

    # Missing asset_id in observation
    with pytest.raises(ValueError, match="must contain an 'asset_id'"):
        builder.add_observation({"sensor": "S1_SAR"})

    # Non-existent parent node for preprocessing
    with pytest.raises(KeyError, match="does not exist"):
        builder.add_preprocessing("nonexistent_node", "filter", {})

    # Invalid confidence range (> 1.0)
    obs = builder.add_observation({"asset_id": "scene-1", "sensor": "S1_SAR"})
    with pytest.raises(ValueError, match="Confidence score must be in range"):
        builder.add_inference(
            input_node_ids=[obs.node_id],
            model_name="model",
            model_version="v1",
            results={},
            confidence=1.5,
        )
