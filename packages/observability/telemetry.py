"""
packages/observability/telemetry.py

Configures OpenTelemetry TracerProvider and FastAPI instrumentation.
"""

import os
from fastapi import FastAPI

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter


def setup_telemetry(app: FastAPI, service_name: str) -> None:
    """
    Configure OpenTelemetry for the given FastAPI app.
    Extracts/injects W3C traceparent headers automatically.
    """
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    # Use OTLP exporter if endpoint is set (e.g. for Jaeger/Honeycomb)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    exporter: SpanExporter
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
    elif os.getenv("OTEL_CONSOLE_EXPORTER", "false").lower() == "true":
        # Fallback to console exporter if explicitly requested
        exporter = ConsoleSpanExporter()
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    # This automatically adds middlewares that extract trace context from
    # incoming requests and create a new span for the request.
    FastAPIInstrumentor.instrument_app(app)

    # Instrument httpx to automatically inject traceparent headers into outgoing requests
    HTTPXClientInstrumentor().instrument()
