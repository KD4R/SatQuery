from fastapi.testclient import TestClient
from packages.contracts.errors import ErrorResponse, ErrorDetail
from packages.contracts.events import EventEnvelope

def test_p1_02_schema_compatibility():
    """
    Test to ensure the schema defined in code matches expected definitions.
    """
    error = ErrorResponse(
        code="TEST_ERROR",
        message="A test error occurred.",
        details=[ErrorDetail(message="detail msg", code="detail_code")],
        retryable=False,
        trace_id="trace-abc"
    )
    
    assert error.code == "TEST_ERROR"
    
    schema = ErrorResponse.model_json_schema()
    assert "code" in schema["properties"]
    assert "message" in schema["properties"]
    assert "details" in schema["properties"]
    assert "retryable" in schema["properties"]
    assert "trace_id" in schema["properties"]

    event_schema = EventEnvelope.model_json_schema()
    assert "event_id" in event_schema["properties"]
    assert "event_type" in event_schema["properties"]
