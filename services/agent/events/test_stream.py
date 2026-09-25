"""Unit tests for agent event emission (P5 Phase C, PRD §2C).

Emission is fire-and-forget by contract: a Redis outage or a bad payload must
be logged and swallowed, never raised into an orchestrator node that would
otherwise fail a real run because telemetry hiccuped.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import services.agent.events.stream as stream
from services.agent.events.stream import (
    emit_acquiring_evidence,
    emit_agent_thought,
    emit_sensor_agreement,
    emit_sensor_disagreement,
)


@pytest.fixture()
def redis_mock():
    client = MagicMock()
    with patch.object(stream, "_get_client", return_value=client):
        yield client


def _published(client) -> list:
    return [json.loads(call.args[1]) for call in client.publish.call_args_list]


@pytest.mark.unit
def test_disagreement_publishes_envelope_on_mission_channel(redis_mock):
    report = SimpleNamespace(
        iou_score=0.31,
        disagreement_percentage=68.0,
        sar_area_sqkm=18.4,
        optical_area_sqkm=6.2,
        likely_anomaly="OPTICAL_CLOUD_SHADOW_CONFUSION",
    )
    emit_sensor_disagreement("m-1", "tr-1", report, "S1_SAR", "S2_OPTICAL")

    (call,) = redis_mock.publish.call_args_list
    assert call.args[0] == "mission:m-1:status"
    envelope = json.loads(call.args[1])
    assert envelope["event_type"] == "SENSOR_DISAGREEMENT"
    assert envelope["producer"] == "agent"
    assert envelope["mission_id"] == "m-1"
    assert envelope["payload"]["iou"] == 0.31
    assert envelope["payload"]["sensors"] == ["S1_SAR", "S2_OPTICAL"]
    # The narrative is the fixed server template, not report-derived free text.
    assert "acquiring an additional radar observation" in envelope["payload"]["reason"]


@pytest.mark.unit
def test_disagreement_without_report_omits_unknown_figures(redis_mock):
    """At arbitration time no masks exist; the event must not invent IoU numbers."""
    emit_sensor_disagreement("m-1", "tr-1", None, "S1_SAR", "S2_OPTICAL")

    envelope = _published(redis_mock)[0]
    assert envelope["event_type"] == "SENSOR_DISAGREEMENT"
    assert envelope["payload"]["disagreement"] is True
    assert "iou" not in envelope["payload"]
    assert "sar_area_sqkm" not in envelope["payload"]


@pytest.mark.unit
def test_agreement_event_clears_with_disagreement_false(redis_mock):
    emit_sensor_agreement("m-1", "tr-1", "S1_SAR", "S2_OPTICAL")

    envelope = _published(redis_mock)[0]
    assert envelope["event_type"] == "SENSOR_DISAGREEMENT"
    assert envelope["payload"]["disagreement"] is False
    assert envelope["payload"]["reason"] != ""


@pytest.mark.unit
def test_publish_failure_is_swallowed_not_raised(redis_mock):
    redis_mock.publish.side_effect = ConnectionError("redis is down")
    # Must not raise — telemetry failures never fail a run.
    emit_agent_thought("m-1", "tr-1", "analyzing", "Running segmentation.")


@pytest.mark.unit
def test_missing_mission_id_is_a_no_op(redis_mock):
    emit_agent_thought(None, "tr-1", "analyzing", "x")
    emit_acquiring_evidence(None, "tr-1", "Low IoU between sensor masks")
    assert redis_mock.publish.call_count == 0


@pytest.mark.unit
def test_empty_reason_is_rejected_by_the_contract(redis_mock):
    emit_acquiring_evidence("m-1", "tr-1", "")
    assert redis_mock.publish.call_count == 0


@pytest.mark.unit
def test_acquiring_evidence_carries_sensors_and_reason(redis_mock):
    emit_acquiring_evidence("m-1", "tr-1", "Optical scene is cloud-obscured", ["S1_SAR"])
    envelope = _published(redis_mock)[0]
    assert envelope["event_type"] == "ACQUIRING_EVIDENCE"
    assert envelope["payload"]["reason"] == "Optical scene is cloud-obscured"
    assert envelope["payload"]["sensors"] == ["S1_SAR"]


@pytest.mark.unit
def test_agent_thought_round_trips_stage_and_text(redis_mock):
    emit_agent_thought("m-1", "tr-1", "analyzing", "Selected the primary acquisition.")
    envelope = _published(redis_mock)[0]
    assert envelope["event_type"] == "AGENT_THOUGHT"
    assert envelope["payload"] == {
        "stage": "analyzing",
        "text": "Selected the primary acquisition.",
    }
