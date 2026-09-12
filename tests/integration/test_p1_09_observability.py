"""
Integration tests for P1-09: Observability & Telemetry.

Verifies:
  - OTel spans are created for requests.
  - Custom JSON logger injects `trace_id` and `span_id`.
  - W3C `traceparent` headers are extracted and propagated.
"""

import json
import logging
from io import StringIO
from fastapi.testclient import TestClient
import pytest

from packages.observability.logging import OTelJsonFormatter


@pytest.mark.integration
def test_p1_09_structured_json_logging_contains_trace_id():
    """
    Verifies that calling a FastAPI route generates JSON logs
    that include standard fields and OTel trace_id.
    """
    from services.gateway.implementation import app

    client = TestClient(app)

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        OTelJsonFormatter(
            "gateway",
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    )

    @app.get("/api/v1/test-log")
    def test_log():
        logger = logging.getLogger("test.logger")
        logger.addHandler(handler)
        logger.propagate = False
        logger.info("This is a test log message")
        return {"status": "ok"}

    resp = client.get("/api/v1/test-log")
    assert resp.status_code == 200

    log_output = stream.getvalue()
    logs = [json.loads(line) for line in log_output.strip().split("\n") if line.strip()]

    assert len(logs) == 1
    log_record = logs[0]

    assert "timestamp" in log_record
    assert log_record["level"] == "INFO"
    assert "trace_id" in log_record
    assert "span_id" in log_record
    assert len(log_record["trace_id"]) == 32
    assert log_record["trace_id"] != "00000000000000000000000000000000"


@pytest.mark.integration
def test_p1_09_incoming_traceparent_is_propagated():
    """
    Verifies that if a client provides a W3C traceparent header,
    the application extracts it and uses it in logs/spans.
    """
    from services.mission.implementation import app

    client = TestClient(app)

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        OTelJsonFormatter(
            "mission",
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    )

    @app.get("/api/v1/test-traceparent")
    def test_trace_log():
        logger = logging.getLogger("test.logger2")
        logger.addHandler(handler)
        logger.propagate = False
        logger.info("Testing traceparent propagation")

        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        return {"trace_id": format(ctx.trace_id, "032x")}

    test_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    traceparent = f"00-{test_trace_id}-00f067aa0ba902b7-01"

    resp = client.get("/api/v1/test-traceparent", headers={"traceparent": traceparent})
    assert resp.status_code == 200
    assert resp.json()["trace_id"] == test_trace_id

    log_output = stream.getvalue()
    logs = [json.loads(line) for line in log_output.strip().split("\n") if line.strip()]

    assert len(logs) == 1
    assert logs[0]["trace_id"] == test_trace_id
