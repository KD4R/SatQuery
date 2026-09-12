"""
packages/contracts/agent.py — Canonical contracts and DTOs for the SatQuery Agent subsystem.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MissionState(BaseModel):
    """
    Canonical MissionState model representing LangGraph / agent state across the workflow.
    """

    mission_id: str = Field(..., description="Unique mission identifier")
    run_id: str = Field(..., description="Execution run identifier")
    organization_id: str = Field(..., description="Tenant organization identifier")
    job_id: Optional[str] = Field(default=None, description="Background job identifier")
    trace_id: Optional[str] = Field(default=None, description="Distributed trace identifier")
    query: str = Field(..., min_length=1, description="Raw natural language prompt")
    sanitized_query: Optional[str] = Field(default=None, description="Sanitized query text")
    status: str = Field(
        default="INITIALIZED",
        description=(
            "Workflow state: INITIALIZED, PLANNING, ACQUIRING, ANALYZING, "
            "GATE_CHECK, COMPLETED, FAILED, CLARIFICATION_REQUIRED"
        ),
    )
    intent: Optional[Dict[str, Any]] = Field(default=None, description="Extracted mission intent")
    aoi: Optional[Dict[str, Any]] = Field(default=None, description="GeoJSON Area of Interest")
    temporal_window: Optional[Dict[str, Any]] = Field(
        default=None, description="Temporal comparison window (baseline vs current)"
    )
    selected_sensors: List[str] = Field(
        default_factory=list,
        description="List of chosen satellite sensors (e.g. S1_SAR, S2_OPTICAL)",
    )
    observation_ids: List[str] = Field(
        default_factory=list, description="IDs of selected satellite observations"
    )
    tool_calls: List[Dict[str, Any]] = Field(
        default_factory=list, description="Audit trail of tool calls executed"
    )
    evidence_graph: Optional[Dict[str, Any]] = Field(
        default=None, description="Structured DAG of evidence nodes and edges"
    )
    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Overall confidence score [0.0 - 1.0]"
    )
    uncertainty_reasons: List[str] = Field(
        default_factory=list, description="Explicit reasons for low confidence or uncertainty"
    )
    synthesized_output: Optional[Dict[str, Any]] = Field(
        default=None, description="Evidence-backed synthesis and explanations"
    )
    errors: List[str] = Field(default_factory=list, description="Encountered errors/warnings")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="System provenance metadata: dataset_id, model_version, processing_version",
    )
    created_at: datetime = Field(default_factory=utc_now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=utc_now, description="Last update timestamp")


# ── Canonical DTOs ────────────────────────────────────────────────────────────


class PlanRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language mission objective")
    mission_id: Optional[str] = Field(default=None, description="Optional associated mission ID")
    aoi: Optional[Dict[str, Any]] = Field(default=None, description="Optional GeoJSON AOI geometry")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual metadata")


class PlanStep(BaseModel):
    step_id: str
    name: str
    description: str
    tool: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class PlanResponse(BaseModel):
    mission_id: str
    intent: Dict[str, Any]
    plan_steps: List[PlanStep]
    selected_sensors: List[str]
    trace_id: Optional[str] = None


class ExecuteRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Mission prompt")
    mission_id: Optional[str] = Field(default=None, description="Mission ID")
    aoi: Optional[Dict[str, Any]] = Field(default=None, description="GeoJSON polygon or bbox")
    temporal_window: Optional[Dict[str, Any]] = Field(default=None, description="Time window")
    budget: Optional[Dict[str, Any]] = Field(
        default=None, description="Tool execution budget constraints"
    )


class ExecuteResponse(BaseModel):
    job_id: str
    mission_id: str
    status: str
    message: str
    trace_id: Optional[str] = None


class SensorDecisionRequest(BaseModel):
    hazard_type: str = Field(
        default="flood", description="Hazard type: flood, fire, cyclone, landslide"
    )
    cloud_cover_percentage: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Cloud cover percentage"
    )
    is_night: bool = Field(default=False, description="Whether observation is at night")
    priority: str = Field(
        default="balanced", description="Optimization priority: accuracy, latency, balanced"
    )


class SensorDecisionResponse(BaseModel):
    primary_sensor: str
    secondary_sensor: Optional[str] = None
    rationale: str
    arbitration_score: float = Field(ge=0.0, le=1.0)
    trace_id: Optional[str] = None


class ConfidenceRequest(BaseModel):
    evidence_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    sensor_type: str = Field(default="SAR")
    cloud_cover: float = Field(default=0.0, ge=0.0, le=100.0)
    resolution_meters: float = Field(default=10.0, gt=0.0)


class ConfidenceResponse(BaseModel):
    confidence_score: float = Field(ge=0.0, le=1.0)
    passed_gate: bool
    uncertainty_factors: List[str] = Field(default_factory=list)
    action: str
    trace_id: Optional[str] = None
