"""
events package — real-time agent event emission onto the mission stream (P5 Phase C).

Narrative strings are fixed server-side templates; user or model free text never
enters the stream. Emission is fire-and-forget and never fails a run.
"""

from services.agent.events.stream import (
    emit_acquiring_evidence,
    emit_agent_thought,
    emit_sensor_agreement,
    emit_sensor_disagreement,
)

__all__ = [
    "emit_acquiring_evidence",
    "emit_agent_thought",
    "emit_sensor_agreement",
    "emit_sensor_disagreement",
]
