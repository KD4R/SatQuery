"""
P6-06 -- OpenTelemetry collector and structured logging

Tests for structured JSON logging, OTel setup, trace context,
and infrastructure config validation.
"""

import json
import logging
import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

pytestmark = pytest.mark.unit


# -- Structured Logging --


class TestStructuredLogging:
    def test_setup_logging_configures_root_logger(self):
        from packages.observability.logging import setup_logging

        root = logging.getLogger()
        original_handlers = root.handlers[:]
        try:
            setup_logging("test-service")
            assert root.level == logging.INFO
            assert len(root.handlers) >= 1
        finally:
            root.handlers = original_handlers

    def test_json_formatter_produces_valid_json(self):
        from packages.observability.logging import OTelJsonFormatter

        formatter = OTelJsonFormatter(
            "test-service",
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["service"] == "test-service"
        assert "timestamp" in parsed
        assert "level" in parsed

    def test_formatter_injects_service_name(self):
        from packages.observability.logging import OTelJsonFormatter

        formatter = OTelJsonFormatter("my-service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        output = json.loads(formatter.format(record))
        assert output["service"] == "my-service"


# -- Telemetry Setup --


class TestTelemetrySetup:
    def test_setup_telemetry_instruments_app(self):
        from packages.observability.telemetry import setup_telemetry

        mock_app = MagicMock()
        with patch("packages.observability.telemetry.FastAPIInstrumentor") as mock_instr:
            with patch("packages.observability.telemetry.HTTPXClientInstrumentor"):
                setup_telemetry(mock_app, "test-svc")
                mock_instr.instrument_app.assert_called_once_with(mock_app)

    def test_console_exporter_when_flag_set(self):
        from packages.observability.telemetry import setup_telemetry

        mock_app = MagicMock()
        env = {"OTEL_CONSOLE_EXPORTER": "true", "OTEL_EXPORTER_OTLP_ENDPOINT": ""}
        with patch.dict(os.environ, env):
            with patch("packages.observability.telemetry.FastAPIInstrumentor"):
                with patch("packages.observability.telemetry.HTTPXClientInstrumentor"):
                    with patch(
                        "packages.observability.telemetry.ConsoleSpanExporter"
                    ) as mock_console:
                        setup_telemetry(mock_app, "test-svc")
                        assert mock_console.called


# -- Trace Context --


class TestTraceContext:
    def test_trace_id_in_log_output(self):
        from opentelemetry.sdk.trace import TracerProvider
        from packages.observability.logging import OTelJsonFormatter

        formatter = OTelJsonFormatter("test-svc")
        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="inside span",
                args=(),
                exc_info=None,
            )
            output = json.loads(formatter.format(record))
            assert "trace_id" in output
            assert len(output["trace_id"]) == 32


# -- OTel Collector Config --


class TestOTelCollectorConfig:
    def test_collector_config_valid_yaml(self):
        with open("infrastructure/docker/otel-collector-config.yml") as f:
            data = yaml.safe_load(f)
        assert "receivers" in data
        assert "processors" in data
        assert "exporters" in data
        assert "service" in data

    def test_collector_has_otlp_receiver(self):
        with open("infrastructure/docker/otel-collector-config.yml") as f:
            data = yaml.safe_load(f)
        assert "otlp" in data["receivers"]
        assert "grpc" in data["receivers"]["otlp"]["protocols"]
        assert "http" in data["receivers"]["otlp"]["protocols"]

    def test_collector_exports_to_prometheus(self):
        with open("infrastructure/docker/otel-collector-config.yml") as f:
            data = yaml.safe_load(f)
        assert "prometheus" in data["exporters"]


# -- Prometheus Config --


class TestPrometheusConfig:
    def test_prometheus_config_valid_yaml(self):
        with open("infrastructure/docker/prometheus.yml") as f:
            data = yaml.safe_load(f)
        assert "global" in data
        assert "scrape_configs" in data

    def test_prometheus_scrapes_api(self):
        with open("infrastructure/docker/prometheus.yml") as f:
            data = yaml.safe_load(f)
        job_names = [job["job_name"] for job in data["scrape_configs"]]
        assert "satquery-api" in job_names


# -- Service Boundary --


class TestP606ServiceBoundary:
    def test_no_service_imports_from_tests(self):
        from pathlib import Path

        for py_file in Path("packages/observability").glob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            content = py_file.read_text(errors="ignore")
            assert "from tests" not in content
