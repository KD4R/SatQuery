# P1 Backend & Gateway — Current Status PRD

Status: **IMPLEMENTED LOCALLY / STACK VERIFICATION BLOCKED**
Owner: P1 backend team  
Merge target: `integration`

## Implemented

- Gateway, mission, auth/RBAC, proxy, rate limiting, security headers, idempotency, and health routes exist.
- Mission/AOI/job contracts and service-boundary tests are present.
- JWT and tenant-scoping helpers are implemented.

## Remaining before sign-off

- Make proxy routes cover every live P2/P3/P4 request used by the generated frontend client.
- Run the authenticated workflow against live Redis/Celery and the complete Compose stack.
- Verify JWT/S2S authentication across Gateway → Mission → Agent → Inference against running services.
- Verify trace/idempotency propagation end to end against running services.

## Evidence

The Gateway no longer emits a synthetic success sequence when Redis is unavailable. It now emits a typed `STATUS_STREAM_UNAVAILABLE` error followed by terminal `done: failed`; terminal statuses are normalized for the browser. Proxy errors now use the canonical top-level `ErrorResponse` shape. Docker-backed chaos tests still require an accessible Docker API.

## Acceptance criteria

Authenticated create-mission → execute → WebSocket progress → terminal result succeeds against the running stack, with Redis enabled and no mock event path selected.

## Required action

Merge the P1 feature branch into `integration`, resolve conflicts, and attach the passing P1 integration test output to the PR.
