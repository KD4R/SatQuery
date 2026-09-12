"""
packages/observability/logging.py

Configures root logger to output structured JSON.
Automatically injects OpenTelemetry trace_id and span_id if an active span exists.
"""

import logging
import sys
from typing import Any, Dict

from opentelemetry import trace  # type: ignore
from pythonjsonlogger.jsonlogger import JsonFormatter


class OTelJsonFormatter(JsonFormatter):
    """
    Extends python-json-logger to inject OpenTelemetry trace context.
    """

    def __init__(self, service_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = service_name

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        # Inject standard fields
        log_record["service"] = self.service_name
        if not log_record.get("level"):
            log_record["level"] = record.levelname

        # Inject OpenTelemetry context if available
        span = trace.get_current_span()
        if span and span.is_recording():
            ctx = span.get_span_context()
            if ctx.is_valid:
                log_record["trace_id"] = format(ctx.trace_id, "032x")
                log_record["span_id"] = format(ctx.span_id, "016x")


def setup_logging(service_name: str, log_level: str = "INFO") -> None:
    """
    Configure the root logger with the OTelJsonFormatter.
    All loggers in the app will inherit this handler.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    formatter = OTelJsonFormatter(
        service_name,
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Ensure third-party libraries aren't too noisy
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
