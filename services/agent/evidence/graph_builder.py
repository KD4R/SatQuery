"""
evidence/graph_builder.py — Deterministic builder for the Evidence Graph DAG.
"""

from typing import Any, Dict, List, Optional
import uuid
from services.agent.evidence.models import (
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    EvidenceNodeType,
)


class EvidenceGraphBuilder:
    """
    Constructs a verifiable DAG of satellite observations, preprocessing, inferences,
    metrics, and causal decisions.
    """

    def __init__(self, mission_id: str, graph_id: Optional[str] = None):
        if not mission_id:
            raise ValueError("mission_id cannot be empty")
        self.mission_id = mission_id
        self.graph_id = graph_id or f"evg_{uuid.uuid4().hex[:8]}"
        self._nodes: Dict[str, EvidenceNode] = {}
        self._edges: List[EvidenceEdge] = []

    def add_observation(self, asset: Dict[str, Any]) -> EvidenceNode:
        asset_id = asset.get("asset_id") or asset.get("id")
        if not asset_id:
            raise ValueError("Observation asset must contain an 'asset_id'")

        node_id = f"obs_{asset_id}"
        node = EvidenceNode(
            node_id=node_id,
            node_type=EvidenceNodeType.OBSERVATION,
            source=asset.get("sensor", "UNKNOWN_SENSOR"),
            data=asset,
            confidence=1.0,
            provenance={
                "observation_id": asset_id,
                "dataset_id": asset.get("dataset_id", "bhoonidhi-stac"),
                "datetime": asset.get("datetime"),
            },
        )
        self._nodes[node_id] = node
        return node

    def add_preprocessing(
        self, obs_node_id: str, op_name: str, params: Dict[str, Any]
    ) -> EvidenceNode:
        if obs_node_id not in self._nodes:
            raise KeyError(f"Parent observation node '{obs_node_id}' does not exist")

        node_id = f"prep_{uuid.uuid4().hex[:6]}"
        node = EvidenceNode(
            node_id=node_id,
            node_type=EvidenceNodeType.PREPROCESSING,
            source=op_name,
            data={"operation": op_name, "parameters": params},
            confidence=1.0,
            provenance={"parent_node": obs_node_id},
        )
        self._nodes[node_id] = node
        self._edges.append(
            EvidenceEdge(source_id=obs_node_id, target_id=node_id, relation="INPUT_TO")
        )
        return node

    def add_inference(
        self,
        input_node_ids: List[str],
        model_name: str,
        model_version: str,
        results: Dict[str, Any],
        confidence: float = 0.90,
    ) -> EvidenceNode:
        if not input_node_ids:
            raise ValueError("Inference requires at least one input node")
        for nid in input_node_ids:
            if nid not in self._nodes:
                raise KeyError(f"Input node '{nid}' does not exist in graph")

        if not (0.0 <= confidence <= 1.0):
            raise ValueError("Confidence score must be in range [0.0, 1.0]")

        node_id = f"inf_{uuid.uuid4().hex[:6]}"
        node = EvidenceNode(
            node_id=node_id,
            node_type=EvidenceNodeType.INFERENCE,
            source=f"{model_name}:{model_version}",
            data=results,
            confidence=confidence,
            provenance={
                "model_name": model_name,
                "model_version": model_version,
                "input_node_ids": input_node_ids,
            },
        )
        self._nodes[node_id] = node
        for nid in input_node_ids:
            self._edges.append(
                EvidenceEdge(source_id=nid, target_id=node_id, relation="DERIVED_FROM")
            )
        return node

    def add_metric(
        self,
        inference_node_id: str,
        metric_name: str,
        value: Any,
        unit: str = "",
    ) -> EvidenceNode:
        if inference_node_id not in self._nodes:
            raise KeyError(f"Inference parent node '{inference_node_id}' does not exist")

        node_id = f"metric_{metric_name}"
        node = EvidenceNode(
            node_id=node_id,
            node_type=EvidenceNodeType.METRIC,
            source="metric_calculator",
            data={"metric_name": metric_name, "value": value, "unit": unit},
            confidence=self._nodes[inference_node_id].confidence,
            provenance={"parent_inference": inference_node_id},
        )
        self._nodes[node_id] = node
        self._edges.append(
            EvidenceEdge(source_id=inference_node_id, target_id=node_id, relation="DERIVED_FROM")
        )
        return node

    def build(self) -> EvidenceGraph:
        return EvidenceGraph(
            graph_id=self.graph_id,
            mission_id=self.mission_id,
            nodes=self._nodes,
            edges=self._edges,
        )
