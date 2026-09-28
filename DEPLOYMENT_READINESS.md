# SatQuery AI - Deployment Readiness

## Engineering Readiness
- **CI/CD & Testing:** Excellent. 573 unit/contract tests exist and are executed. The P6 CI/CD pipelines are properly configured for immutable image tagging and rollbacks.
- **Observability:** Excellent. OpenTelemetry tracing and Prometheus metric families are correctly established in code.
- **Code Organization:** Good. The service boundaries and monorepo structure align with the PRDs.

## Runtime Readiness
- **Frontend integration:** The frontend is entirely disjointed from the backend. The UI is a mockup using `setTimeout` and hardcoded state objects. It cannot communicate with live backend services.
- **Inference Models:** Actual ML model artifacts are missing. `infrastructure/models/` is empty. The inference service explicitly falls back to returning deterministic baseline degraded results.
- **Provider APIs:** Live API integration with Bhoonidhi is unstable or bypassed, relying on a `FixtureFallbackManager` to return pinned JSON files instead of live catalog results.

## External Dependencies
- Missing live access to Earth Observation data APIs.
- Missing required model weight files.

## Overall Deployment Readiness
**NOT READY.** 
While the engineering practices, CI pipelines, and backend service skeletons are highly mature, the product logic is disconnected. The system cannot be deployed to production as a working application because it will only execute static demo paths.

## Status update (2026-09-28, branch `cloud/console-routing-prd-pass`)

The "frontend is a mockup" finding above is out of date. `/dashboard` (the single
mission console) submits `POST /agent/execute` and polls `GET /agent/runs/{id}`
through the gateway; the fixture demo is a separate, badged path behind
`NEXT_PUBLIC_DEMO_MODE`. Verified in this pass: `npm run typecheck`, `lint`,
`test` (100), `build` and Playwright (34, demo mode) pass; gateway/agent/auth unit
and integration tests pass except the pre-existing failures listed in the PR
notes (they need a live Redis/compose stack, or reference the removed
`FixtureFallbackManager`).

Still blocking a real deployment: no Alembic migrations exist; no gateway
readiness endpoint (only liveness `/api/v1/health`); no observations, model
weights or live Bhoonidhi access, so live runs fail honestly with "No
observations found"; `AGENT_EXECUTION_MODE` defaults to a daemon thread; Docker
images were not built in this pass (no daemon available).
