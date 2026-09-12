"""
evidence package — Evidence Graph, uncertainty gates, and disagreement analysis for SatQuery AI.
"""

from evidence.disagreement import DisagreementReport, analyze_sensor_disagreement
from evidence.graph_builder import EvidenceGraphBuilder
from evidence.models import (
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    EvidenceNodeType,
)

__all__ = [
    "DisagreementReport",
    "EvidenceEdge",
    "EvidenceGraph",
    "EvidenceGraphBuilder",
    "EvidenceNode",
    "EvidenceNodeType",
    "analyze_sensor_disagreement",
]
