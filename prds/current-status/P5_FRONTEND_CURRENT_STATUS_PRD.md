# P5 Frontend — Current Status PRD

Status: **BUILD PASS / INTEGRATION BLOCKED**  
Owner: P5 frontend team  
Merge target: `integration`

## Implemented

- Next.js application, dashboard routes, generated-client adapter, landing experience, map/evidence/report surfaces, and production build configuration exist.
- `npm.cmd run build` passes in the current checkout.

## Remaining before sign-off

- Ensure live mode submits the actual ExecuteRequest through the Gateway.
- Remove timer-driven fabricated state from the release path.
- Consume P1 WebSocket events for timeline, evidence, status, errors, and completion.
- Render live COG/TiTiler layers instead of static fixture imagery.
- Keep demo mode visibly isolated and never use it as a live-call fallback.
- Add browser acceptance coverage for query → progress → evidence → map → report.
- Restore or intentionally document the frontend service in the production Compose topology.

## Evidence

The frontend build passes, but live backend execution and map rendering have not been verified against the full stack.

## Acceptance criteria

A browser session with a valid token can submit a real flood query, observe live progress, display provenance/evidence, render the returned map layer, and show typed failure states.

## Required action

Merge the P5 feature branch into `integration` after P1 WebSocket and P4 TiTiler contracts are stable.
