# ADR-0006: Internal Service-to-Service Client with Resilience Patterns

**Status:** Accepted  
**Date:** 2026-09-11  
**Deciders:** Platform Engineering Team  

---

## Context

Services within SatQuery AI need to call each other (e.g., Gateway forwarding to Mission Service, Mission Service notifying Agent workers). These internal calls must:
- Propagate auth context and trace IDs automatically.
- Handle transient network failures gracefully without cascading failures.
- Present a uniform error surface regardless of which downstream service failed.

## Decision

We implement a shared `InternalClient` in `packages/shared/client.py` that all services use for internal HTTP calls:

### Features

1. **Automatic header propagation**: Every request carries the caller's `Authorization` (S2S token) and `X-Trace-Id` (OTel trace ID).
2. **Strict timeouts**: `httpx.AsyncClient` with `timeout=5.0` seconds. No request can block a thread indefinitely.
3. **Exponential backoff retries** (via `tenacity`): Transient errors (`httpx.TimeoutException`, `ConnectError`, `5xx` from downstream) are retried up to 3 times with jitter.
4. **Circuit Breaker**: A stateful `CircuitBreaker` per downstream service:
   - **CLOSED** (normal): requests pass through.
   - **OPEN** (failing): after 3 consecutive failures, requests fail immediately for 10 seconds (no network calls made).
   - **HALF-OPEN** (recovery probe): one request is attempted; success resets to CLOSED, failure extends OPEN.

## OWASP Alignment

- **A05 Security Misconfiguration**: S2S tokens are short-lived (5 min) and scoped to specific operations. The client never reuses user-facing tokens for internal calls.
- **A10 Server-Side Request Forgery (SSRF)**: Internal client only accepts pre-configured base URLs from environment variables — no user-supplied URLs are ever passed to `InternalClient`.

## Consequences

### Positive
- Resilience patterns are in one place — adding a new internal call automatically gets timeouts, retries, and circuit breaking.
- Circuit Breaker prevents a failing downstream from overwhelming the upstream (cascading failure protection).
- Uniform `InternalServiceError` exception type simplifies error handling in callers.

### Negative / Mitigations
- In-memory Circuit Breaker state is not shared across process replicas. Mitigated by short `OPEN` windows (10s) — each pod independently discovers the outage within one cycle.
- For P1, the Circuit Breaker is in-memory. Production can evolve to Redis-backed shared state.

## Alternatives Considered

| Option | Reason Rejected |
|---|---|
| Raw `httpx` calls in each service | No consistent timeout, retry, or circuit breaking — each service would need to re-implement |
| Service mesh (Istio/Linkerd) | Infrastructure complexity inappropriate for P1; can be layered on later |
| Resilience4j (Java-style) | Not idiomatic Python; `tenacity` is the established Python retry library |
