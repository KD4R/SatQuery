# ADR-0005: OpenTelemetry for Distributed Tracing and Structured JSON Logging

**Status:** Accepted  
**Date:** 2026-09-11  
**Deciders:** Platform Engineering Team  

---

## Context

SatQuery AI spans multiple services (Gateway, Mission, Agent, EO-Data). Debugging production issues requires the ability to correlate log lines across service boundaries for a single user request.

## Decision

We adopt **OpenTelemetry (OTel)** as the observability standard for all SatQuery services:

1. **Distributed tracing**: Every inbound HTTP request generates an OTel span. The `traceparent` W3C header is propagated to downstream calls via the `InternalClient`.
2. **Structured JSON logging**: Every log line is emitted as a JSON object. The `trace_id` and `span_id` from the active OTel span are injected into each log record by `OTelJsonFormatter`.
3. **Centralised setup**: `packages/observability/` provides `setup_logging()` and `setup_telemetry()` — services call these once at startup with a single service name argument.

## Log Format

```json
{
  "timestamp": "2026-09-11T17:00:00.000Z",
  "level": "INFO",
  "name": "services.mission.routers.missions",
  "message": "Mission created: id=abc org=tenant_1",
  "service": "mission",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

## OWASP Alignment

- **A09 Security Logging and Monitoring Failures**: Every request is logged with a stable `trace_id`. Auth failures, RBAC denials, and 5xx errors all emit structured log entries that can be forwarded to a SIEM (e.g., Datadog, Splunk).
- **No secret leakage**: Tokens, keys, and PII are never logged. Error messages reference codes (`TOKEN_EXPIRED`, `INSUFFICIENT_PERMISSIONS`) rather than raw exceptions.

## Consequences

### Positive
- Single `trace_id` threads through Gateway → Mission → Agent logs — trivial to reconstruct a full request flow.
- OTel is vendor-neutral — exporters can be swapped (Jaeger, Zipkin, Datadog, OTLP) without code changes.
- JSON log format is immediately parseable by log aggregation tools (Loki, CloudWatch, Datadog Logs).

### Negative / Mitigations
- Small per-request overhead for span creation (~microseconds). Acceptable for our latency targets.
- OTel SDK adds ~10 MB to the Docker image. Acceptable.

## Alternatives Considered

| Option | Reason Rejected |
|---|---|
| Plain text logging | Cannot be reliably parsed by log aggregators; no trace correlation |
| Datadog APM SDK directly | Vendor lock-in; OTel gives us portability |
| Zipkin B3 headers | W3C `traceparent` is the modern standard; better ecosystem support |
