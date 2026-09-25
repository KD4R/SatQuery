from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc)


# ── Agent stream event types (P5 Phase C, PRD §2C) ───────────────────────────
# Sent over the mission WebSocket (WS /ws/v1/missions/{id}) inside an
# EventEnvelope. The UI renders these as live agent-activity toasts.
EventType = Literal[
    "SENSOR_DISAGREEMENT",
    "ACQUIRING_EVIDENCE",
    "AGENT_THOUGHT",
    "STATUS_UPDATE",
]


class SensorDisagreementPayload(BaseModel):
    """Payload for SENSOR_DISAGREEMENT — the sensors disagree on water extent.

    Emitted in two honest forms: at arbitration time with only the sensors and
    the reason (no masks have been compared yet), and after analysis with the
    per-sensor areas and the IoU of the two water masks. Fields the emitting
    stage cannot know stay absent — never filled with placeholders (P5: a gap
    is information).
    """

    sensors: list[str] = Field(
        ..., min_length=2, description="The conflicting sensors, e.g. [S1_SAR, S2_OPTICAL]"
    )
    reason: str = Field(
        ...,
        min_length=1,
        description=(
            "Operator-readable narrative. Never user- or model-generated free "
            "text: the emitting node sets it from a fixed server-side template."
        ),
    )
    disagreement: bool = Field(
        default=True,
        description="False on the agreement counterpart, which clears the UI warning.",
    )
    iou: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="IoU of the two water masks, when compared"
    )
    disagreement_percentage: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Percentage of the union extent in conflict"
    )
    sar_area_sqkm: Optional[float] = Field(default=None, ge=0.0)
    optical_area_sqkm: Optional[float] = Field(default=None, ge=0.0)
    likely_anomaly: Optional[str] = Field(
        default=None,
        description=(
            "Physical cause hypothesised by the analysis, e.g. "
            "RADAR_SHADOW_TERRAIN_ARTEFACT or OPTICAL_CLOUD_SHADOW_CONFUSION"
        ),
    )


class AcquiringEvidencePayload(BaseModel):
    """Payload for ACQUIRING_EVIDENCE — the agent is fetching more data."""

    reason: str = Field(
        ...,
        min_length=1,
        description=(
            "Why more evidence is needed, in operator-readable form. Never user- "
            "or model-generated free text: the emitting node must set it from a "
            "fixed template so the stream cannot carry injected content to the DOM."
        ),
    )
    sensors: list[str] = Field(
        default_factory=list, description="Sensors being queried, when known"
    )


class AgentThoughtPayload(BaseModel):
    """Payload for AGENT_THOUGHT — one step of the agent's visible reasoning.

    Same template rule as ACQUIRING_EVIDENCE: `text` is set by the emitting node
    from fixed strings, so the browser can render it as text with no sanitiser
    roulette (A03 by construction, not by scrubbing).
    """

    stage: str = Field(..., min_length=1, description="Orchestrator node, e.g. analyzing")
    text: str = Field(..., min_length=1)


class EventEnvelope(BaseModel):
    """
    Canonical EventEnvelope for inter-service async events.
    """

    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Type of event (e.g., INFERENCE_COMPLETED)")
    timestamp: datetime = Field(default_factory=utc_now, description="Event occurrence time")
    trace_id: Optional[str] = Field(default=None, description="Correlation trace ID")
    mission_id: Optional[str] = Field(default=None, description="Associated mission ID")
    producer: str = Field(..., description="Service producing the event")
    schema_version: str = Field(default="1.0", description="Schema version")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific payload")

    @field_validator("payload")
    @classmethod
    def _payload_must_be_json_safe(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        """Reject None values inside the payload dict.

        None is the one value that silently changes meaning between Python and
        JSON tooling (None vs null vs missing); payloads on the stream carry
        displayable fields, and an explicit absence beats an ambiguous null.
        Nested structures are validated by the payload models above.
        """
        for key, item in value.items():
            if item is None:
                raise ValueError(f"payload[{key!r}] must not be null; omit the key instead")
        return value
