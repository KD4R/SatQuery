"""
Contract compatibility tests for P1-02 canonical schema freeze.
"""

import pytest

from packages.contracts.errors import ErrorResponse, ErrorDetail
from packages.contracts.events import EventEnvelope


@pytest.mark.contract
def test_p1_02_schema_compatibility():
    """ErrorResponse JSON schema has all required fields."""
    schema = ErrorResponse.model_json_schema()
    required_fields = {"code", "message", "details", "retryable", "trace_id"}
    assert required_fields.issubset(schema["properties"].keys())


@pytest.mark.contract
def test_p1_02_event_envelope_schema_compatibility():
    """EventEnvelope JSON schema has all required fields."""
    schema = EventEnvelope.model_json_schema()
    required_fields = {"event_id", "event_type", "timestamp", "producer", "payload"}
    assert required_fields.issubset(schema["properties"].keys())


@pytest.mark.contract
def test_p1_02_error_response_serialization():
    """ErrorResponse serializes to canonical JSON shape."""
    error = ErrorResponse(
        code="VALIDATION_ERROR",
        message="Input is invalid",
        details=[ErrorDetail(message="field required", code="FIELD_REQUIRED")],
        retryable=False,
        trace_id="trace-abc",
    )
    data = error.model_dump()
    assert data["code"] == "VALIDATION_ERROR"
    assert data["details"][0]["code"] == "FIELD_REQUIRED"
    assert data["retryable"] is False


@pytest.mark.contract
def test_p1_02_event_envelope_serialization():
    """EventEnvelope serializes to canonical JSON shape."""
    event = EventEnvelope(
        event_id="evt-001",
        event_type="MISSION_STARTED",
        producer="mission-service",
        mission_id="mission-xyz",
        trace_id="trace-001",
        payload={"status": "running"},
    )
    data = event.model_dump()
    assert data["event_type"] == "MISSION_STARTED"
    assert data["mission_id"] == "mission-xyz"
    assert data["payload"]["status"] == "running"
