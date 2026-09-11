"""
Contract unit tests for canonical schemas (P1-02).
"""
import pytest
from pydantic import ValidationError

from packages.contracts.errors import ErrorResponse, ErrorDetail
from packages.contracts.events import EventEnvelope


@pytest.mark.contract
def test_freeze_canonical_api_error_and_event_contracts_valid():
    """Valid ErrorResponse and EventEnvelope instances can be constructed."""
    error = ErrorResponse(
        code="INTERNAL_ERROR",
        message="Something went wrong",
        details=[ErrorDetail(message="DB timeout", code="DB_TIMEOUT")],
        retryable=True,
        trace_id="trace-123",
    )
    assert error.code == "INTERNAL_ERROR"
    assert error.retryable is True
    assert len(error.details) == 1

    event = EventEnvelope(
        event_id="evt-456",
        event_type="MISSION_CREATED",
        producer="mission-service",
        payload={"foo": "bar"},
    )
    assert event.event_type == "MISSION_CREATED"
    assert event.schema_version == "1.0"


@pytest.mark.contract
def test_freeze_canonical_api_error_and_event_contracts_invalid_input():
    """Missing required fields raise ValidationError."""
    with pytest.raises(ValidationError):
        ErrorResponse(retryable=False)  # missing code, message

    with pytest.raises(ValidationError):
        EventEnvelope(event_type="TEST")  # missing event_id and producer


@pytest.mark.contract
def test_error_response_defaults():
    """ErrorResponse defaults are sane."""
    error = ErrorResponse(code="NOT_FOUND", message="Resource not found")
    assert error.details == []
    assert error.retryable is False
    assert error.trace_id is None


@pytest.mark.contract
def test_event_envelope_timestamp_is_set():
    """EventEnvelope auto-sets timestamp."""
    event = EventEnvelope(
        event_id="evt-789",
        event_type="JOB_QUEUED",
        producer="gateway-service",
    )
    assert event.timestamp is not None
