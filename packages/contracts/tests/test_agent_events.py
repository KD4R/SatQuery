"""Contract tests for the agent stream event payloads (P5 Phase C, PRD §2C)."""

import pytest
from pydantic import ValidationError

from packages.contracts.events import (
    AcquiringEvidencePayload,
    AgentThoughtPayload,
    EventEnvelope,
    SensorDisagreementPayload,
)


@pytest.mark.contract
def test_sensor_disagreement_payload_round_trips_arbitration_figures():
    payload = SensorDisagreementPayload(
        sensors=["S1_SAR", "S2_OPTICAL"],
        reason="Optical and SAR disagree on flood extent — acquiring an additional radar "
        "observation to arbitrate.",
        iou=0.31,
        disagreement_percentage=68.0,
        sar_area_sqkm=18.4,
        optical_area_sqkm=6.2,
        likely_anomaly="OPTICAL_CLOUD_SHADOW_CONFUSION",
    )
    envelope = EventEnvelope(
        event_id="evt-1",
        event_type="SENSOR_DISAGREEMENT",
        producer="agent",
        mission_id="m-1",
        trace_id="tr-1",
        payload=payload.model_dump(),
    )
    assert envelope.payload["iou"] == 0.31
    assert envelope.payload["sensors"] == ["S1_SAR", "S2_OPTICAL"]


@pytest.mark.contract
def test_sensor_disagreement_payload_rejects_out_of_range_iou():
    with pytest.raises(ValidationError):
        SensorDisagreementPayload(
            sensors=["S1_SAR", "S2_OPTICAL"],
            iou=1.5,
            disagreement_percentage=10.0,
            sar_area_sqkm=1.0,
            optical_area_sqkm=1.0,
        )


@pytest.mark.contract
def test_sensor_disagreement_payload_requires_both_sensors():
    with pytest.raises(ValidationError):
        SensorDisagreementPayload(
            sensors=["S1_SAR"],
            iou=0.5,
            disagreement_percentage=10.0,
            sar_area_sqkm=1.0,
            optical_area_sqkm=1.0,
        )


@pytest.mark.contract
def test_acquiring_evidence_payload_requires_reason():
    assert (
        AcquiringEvidencePayload(reason="Low IoU between sensors; acquiring radar").reason
        != ""
    )
    with pytest.raises(ValidationError):
        AcquiringEvidencePayload(reason="")


@pytest.mark.contract
def test_agent_thought_payload_requires_stage_and_text():
    AgentThoughtPayload(stage="analyzing", text="Running water segmentation.")
    with pytest.raises(ValidationError):
        AgentThoughtPayload(stage="analyzing", text="")
    with pytest.raises(ValidationError):
        AgentThoughtPayload(stage="", text="x")


@pytest.mark.contract
def test_envelope_rejects_null_payload_values():
    """Null payload values are ambiguous on the wire; omit the key instead."""
    with pytest.raises(ValidationError):
        EventEnvelope(
            event_id="evt-2",
            event_type="AGENT_THOUGHT",
            producer="agent",
            payload={"stage": "analyzing", "text": None},
        )


@pytest.mark.contract
def test_existing_status_envelopes_still_validate():
    """The validator must not break pre-existing envelope usage."""
    event = EventEnvelope(event_id="evt-3", event_type="JOB_QUEUED", producer="gateway")
    assert event.payload == {}
    assert event.schema_version == "1.0"
