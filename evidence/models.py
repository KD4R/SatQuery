"""
evidence/models.py — Evidence Graph models, nodes, edges, and provenance structures.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List
from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class EvidenceNodeType(str, Enum):
    OBSERVATION = "OBSERVATION"
    PREPROCESSING = "PREPROCESSING"
    INFERENCE = "INFERENCE"
    METRIC = "METRIC"
    DECISION = "DECISION"
    DISAGREEMENT = "DISAGREEMENT"


class EvidenceEdge(BaseModel):
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relation: str = Field(
        ..., description="Relationship: DERIVED_FROM, INPUT_TO, VALIDATED_BY, CONTRADICTS"
    )


class EvidenceNode(BaseModel):
    node_id: str = Field(..., description="Unique evidence node ID")
    node_type: EvidenceNodeType
    source: str = Field(..., description="Producer module, sensor, or model name")
    data: Dict[str, Any] = Field(default_factory=dict, description="Payload data")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Lineage metadata: observation_ids, model_version, dataset_id",
    )
    timestamp: str = Field(default_factory=utc_now_iso)


class EvidenceGraph(BaseModel):
    graph_id: str
    mission_id: str
    nodes: Dict[str, EvidenceNode] = Field(default_factory=dict)
    edges: List[EvidenceEdge] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
