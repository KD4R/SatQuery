import pytest
from pydantic import ValidationError
from packages.contracts.errors import ErrorResponse, ErrorDetail
from packages.contracts.events import EventEnvelope

def test_freeze_canonical_api_error_and_event_contracts_valid():
    error = ErrorResponse(
        code="INTERNAL_ERROR",
        message="Something went wrong",
        details=[ErrorDetail(message="DB timeout", code="DB_TIMEOUT")],
        retryable=True,
        trace_id="trace-123"
    )
    assert error.code == "INTERNAL_ERROR"
    assert error.retryable is True

    event = EventEnvelope(
        event_id="evt-456",
        event_type="MISSION_CREATED",
        producer="mission-service",
        payload={"foo": "bar"}
    )
    assert event.event_type == "MISSION_CREATED"

def test_freeze_canonical_api_error_and_event_contracts_invalid_input():
    with pytest.raises(ValidationError):
        # Missing required fields
        ErrorResponse(retryable=False)

    with pytest.raises(ValidationError):
        EventEnvelope(event_type="TEST") # missing event_id and producer
