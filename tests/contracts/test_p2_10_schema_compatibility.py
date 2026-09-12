"""
tests/contracts/test_p2_10_schema_compatibility.py
Contract compatibility tests for P2-10: Evidence Graph schemas.
"""

import pytest
from services.agent.evidence.models import EvidenceEdge, EvidenceGraph, EvidenceNode


@pytest.mark.contract
def test_p2_10_schema_compatibility():
    """EvidenceGraph, EvidenceNode, and EvidenceEdge schemas conform to contract."""
    node_schema = EvidenceNode.model_json_schema()
    expected_node = {
        "node_id",
        "node_type",
        "source",
        "data",
        "confidence",
        "provenance",
        "timestamp",
    }
    assert expected_node.issubset(node_schema["properties"].keys())

    edge_schema = EvidenceEdge.model_json_schema()
    expected_edge = {"source_id", "target_id", "relation"}
    assert expected_edge.issubset(edge_schema["properties"].keys())

    graph_schema = EvidenceGraph.model_json_schema()
    expected_graph = {"graph_id", "mission_id", "nodes", "edges", "created_at"}
    assert expected_graph.issubset(graph_schema["properties"].keys())
