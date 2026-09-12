# SatQuery AI — SIH 2026 Frontend

Final P5 frontend foundation for the SatQuery AI geospatial command center, aligned to the supplied P5 and P4 engineering PRDs.

## Included

- Next.js + React + TypeScript + Tailwind-compatible CSS architecture
- Map-first Mission Control with MapLibre
- Mission Copilot with keyboard shortcut, templates and running state
- AOI / change / confidence map controls and AOI draw-mode UX
- Before/after-ready observation workspace surface
- Sensor arbitration: Optical vs SAR with route rationale
- Confidence / uncertainty + human-in-loop gate
- WHY? evidence chain with provenance fields
- Auditable run timeline and trace drawer
- Mission history / monitoring / report navigation states
- Persistent monitoring control
- Decision brief + GeoJSON/report/export action surfaces
- Responsive desktop/tablet/mobile layouts
- Full dark + light mode with persisted preference
- Gateway-only API adapter under `lib/api.ts`
- Explicit failure-aware API helper; no private service calls

## Run

```bash
npm install
npm run dev
```

Open http://localhost:3000.

## Backend

Set:

```env
NEXT_PUBLIC_GATEWAY_URL=https://your-gateway.example/api/v1
```

The browser integration is intentionally routed through the Gateway only, matching the P5 PRD. Wire the generated TypeScript contracts to the exact team Gateway DTOs when they are frozen.

## Demo mode

The UI contains deterministic presentation fixtures for the flagship flood flow so the frontend is runnable before the other services are available. These values are **demo fixtures**, not claims from a live backend. Replace them with Gateway responses for a real judging deployment.

## Flagship flow

Query → Mission Plan → AOI → Observation Discovery → Optical/SAR Decision → Analysis → Evidence → Map → Confidence → Report.

## Important integration notes

- Long-running work should consume backend 202/job IDs and WebSocket/SSE progress rather than inventing progress in the client.
- Preserve `trace_id`, `mission_id`, `run_id`, `job_id`, `organization_id`, `model_version`, and `dataset_id` wherever supplied by the Gateway.
- Keep secrets and private service URLs out of the browser.
- Do not render arbitrary HTML from model output.
