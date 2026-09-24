# P1 Backend & Gateway — Current Status PRD

Status: **PARTIAL / BLOCKED for release**  
Owner: P1 backend team  
Merge target: `integration`

## Implemented

- Gateway, mission, auth/RBAC, proxy, rate limiting, security headers, idempotency, and health routes exist.
- Mission/AOI/job contracts and service-boundary tests are present.
- JWT and tenant-scoping helpers are implemented.

## Remaining before sign-off

- Make proxy routes cover every live P2/P3/P4 request used by the generated frontend client.
- Make the mission WebSocket consume live Redis/Celery events and emit a deterministic terminal `done` event.
- Remove or strictly isolate mock WebSocket sequences from production configuration.
- Verify JWT/S2S authentication across Gateway → Mission → Agent → Inference.
- Verify error responses and trace/idempotency propagation end to end.

## Evidence

The WebSocket integration test currently receives `status_update` where it expects `done`. Docker-backed chaos tests cannot run while the Docker API is unavailable.

## Acceptance criteria

Authenticated create-mission → execute → WebSocket progress → terminal result succeeds against the running stack, with Redis enabled and no mock event path selected.

## Required action

Merge the P1 feature branch into `integration`, resolve conflicts, and attach the passing P1 integration test output to the PR.
