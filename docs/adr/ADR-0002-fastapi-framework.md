# ADR-0002: FastAPI as the HTTP Service Framework

**Status:** Accepted  
**Date:** 2026-09-11  
**Deciders:** Platform Engineering Team  

---

## Context

SatQuery AI services need an HTTP framework that supports:
- High-throughput async I/O (satellite imagery pipelines, ML inference results)
- First-class OpenAPI / JSON Schema generation for frontend client code-gen
- Type-safe request/response validation
- WebSocket support for real-time job status streams

## Decision

We use **FastAPI** (backed by Starlette and Pydantic v2) for all internal HTTP services.

## Rationale

| Requirement | FastAPI | Django REST | Flask |
|---|---|---|---|
| Async I/O (asyncio) | ✅ Native | ⚠️ ASGI add-on | ⚠️ Add-on |
| OpenAPI auto-generation | ✅ Built-in | ⚠️ drf-spectacular | ❌ Manual |
| Pydantic schema validation | ✅ Native | ❌ Serializers | ❌ marshmallow |
| WebSocket support | ✅ Starlette | ⚠️ channels | ⚠️ flask-sock |
| Type-checking / mypy | ✅ Excellent | ⚠️ Moderate | ⚠️ Moderate |
| Performance (req/s) | ✅ Very high | ⚠️ Medium | ⚠️ Medium |

## OWASP Alignment

- **A03 Injection**: Pydantic v2 field validators with `max_length`, `regex`, and control-character rejection are enforced at the framework boundary — no raw data reaches business logic.
- **A05 Security Misconfiguration**: FastAPI's `APIRouter` scoping and dependency injection make it structurally difficult to forget an auth dependency on a route.

## Consequences

### Positive
- Auto-generated OpenAPI schemas power our frontend TypeScript client generation (`npx openapi-generator-cli`).
- `Depends()` injection pattern enables testable, composable auth/RBAC/tenant-isolation without touching handler code.
- `pytest` + `TestClient` / `AsyncClient` integration is first-class.

### Negative / Mitigations
- FastAPI is newer than Django; fewer third-party plugins. Mitigated by direct Starlette middleware access and Python ecosystem breadth.
- No built-in ORM. Mitigated by repository pattern (`packages/repositories/`); SQLAlchemy wired in separately.

## Alternatives Considered

| Option | Reason Rejected |
|---|---|
| Django REST Framework | Synchronous by default; heavyweight ORM coupling; no built-in OpenAPI generation |
| Flask + marshmallow | Manual OpenAPI wiring; no async support; more boilerplate |
| gRPC / Protobuf | Binary protocol unsuitable for browser clients and external integrations |
