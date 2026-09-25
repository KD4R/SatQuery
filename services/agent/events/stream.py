"""
events/stream.py — agent event emission onto the mission stream (P5 Phase C, PRD §2C).

Publishes EventEnvelope messages to the Redis channel the gateway's WebSocket
bridge (services/gateway/routers/missions_ws.py) already subscribes to:
mission:{mission_id}:status. Envelope-shaped messages pass through the bridge
to the browser verbatim, so the UI receives the full payload.

Emission is fire-and-forget by construction: the orchestrator nodes are
synchronous and a telemetry publish must never fail a run, so every failure is
logged and swallowed. The channel is resolved from the mission id — never from
query text or any other user-controlled string (A10: no user input in infra
selectors). Narrative strings come from fixed server-side templates; user or
model free text never enters the stream (A03 by construction).
"""

import logging
import os
import uuid
from typing import Any, Dict, Optional

from packages.contracts.events import (
    AcquiringEvidencePayload,
    AgentThoughtPayload,
    EventEnvelope,
    SensorDisagreementPayload,
)

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Fixed templates. The UI renders these verbatim as text, so they must stay
# prose that the server authored — never interpolated user content.
_DISAGREEMENT_REASON = (
    "Optical and SAR disagree on flood extent — acquiring an additional radar "
    "observation to arbitrate."
)
_AGREEMENT_REASON = "Sensors agree on the observed extent; no extra acquisition needed."

_client = None


def _get_client():
    """Lazily create the Redis client; a missing Redis is a logged no-op."""
    global _client
    if _client is None:
        try:
            import redis

            _client = redis.from_url(_REDIS_URL, decode_responses=True)
        except Exception as exc:  # pragma: no cover - depends on local env
            logger.warning("Agent event stream disabled (redis unavailable): %s", exc)
            return None
    return _client


def _emit(
    event_type: str,
    mission_id: Optional[str],
    trace_id: Optional[str],
    payload: Dict[str, Any],
) -> None:
    """Build the envelope and publish it, swallowing every failure."""
    if not mission_id:
        return
    try:
        envelope = EventEnvelope(
            event_id=f"evt-{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            trace_id=trace_id,
            mission_id=mission_id,
            producer="agent",
            payload=payload,
        )
        client = _get_client()
        if client is None:
            return
        client.publish(f"mission:{mission_id}:status", envelope.model_dump_json())
    except Exception as exc:
        # Telemetry must never break the run: log and drop.
        logger.warning("Agent event publish failed (mission=%s): %s", mission_id, exc)


def emit_sensor_disagreement(
    mission_id: Optional[str],
    trace_id: Optional[str],
    report: Any = None,
    primary_sensor: str = "S1_SAR",
    secondary_sensor: str = "S2_OPTICAL",
) -> None:
    """Publish SENSOR_DISAGREEMENT.

    Without a DisagreementReport (arbitration time, before any masks exist) the
    event carries only sensors and the fixed reason — figures the stage does
    not have stay absent, never invented. With a report it carries the IoU and
    areas the analysis produced.
    """
    fields: Dict[str, Any] = {
        "sensors": [primary_sensor, secondary_sensor],
        "reason": _DISAGREEMENT_REASON,
        "disagreement": True,
    }
    if report is not None:
        try:
            fields.update(
                SensorDisagreementPayload(
                    sensors=fields["sensors"],
                    reason=_DISAGREEMENT_REASON,
                    iou=float(report.iou_score),
                    disagreement_percentage=float(report.disagreement_percentage),
                    sar_area_sqkm=float(report.sar_area_sqkm),
                    optical_area_sqkm=float(report.optical_area_sqkm),
                    likely_anomaly=report.likely_anomaly,
                ).model_dump(exclude_none=True)
            )
        except Exception as exc:
            logger.warning("SENSOR_DISAGREEMENT report payload invalid: %s", exc)
            return
    _emit("SENSOR_DISAGREEMENT", mission_id, trace_id, fields)


def emit_sensor_agreement(
    mission_id: Optional[str],
    trace_id: Optional[str],
    primary_sensor: str = "S1_SAR",
    secondary_sensor: str = "S2_OPTICAL",
) -> None:
    """Publish the agreement counterpart, so the UI can retire the warning."""
    _emit(
        "SENSOR_DISAGREEMENT",
        mission_id,
        trace_id,
        {
            "sensors": [primary_sensor, secondary_sensor],
            "reason": _AGREEMENT_REASON,
            "disagreement": False,
        },
    )


def emit_agent_thought(
    mission_id: Optional[str],
    trace_id: Optional[str],
    stage: str,
    text: str,
) -> None:
    """Publish an AGENT_THOUGHT from a fixed, node-authored template string."""
    try:
        payload = AgentThoughtPayload(stage=stage, text=text)
    except Exception as exc:
        logger.warning("AGENT_THOUGHT payload invalid: %s", exc)
        return
    _emit("AGENT_THOUGHT", mission_id, trace_id, payload.model_dump())


def emit_acquiring_evidence(
    mission_id: Optional[str],
    trace_id: Optional[str],
    reason: str,
    sensors: Optional[list] = None,
) -> None:
    """Publish ACQUIRING_EVIDENCE from a fixed, node-authored template string."""
    try:
        payload = AcquiringEvidencePayload(reason=reason, sensors=list(sensors or []))
    except Exception as exc:
        logger.warning("ACQUIRING_EVIDENCE payload invalid: %s", exc)
        return
    _emit("ACQUIRING_EVIDENCE", mission_id, trace_id, payload.model_dump())


__all__ = [
    "emit_acquiring_evidence",
    "emit_agent_thought",
    "emit_sensor_agreement",
    "emit_sensor_disagreement",
]
