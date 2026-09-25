# P5: Frontend UX Work Package (Atharv)

## Objective
Finalize the migration to the generated OpenAPI client, strip all `setTimeout` mocks, and wire the Next.js frontend directly into the live P1 Gateway.

## Tasks

### 1. Focus on `feat/p5-frontend-migration`
- The `feat/p5-frontend-migration` branch contains the critical `lib/api/generated/` client and `backendAdapter.ts`. **Do not use `main` or the older `mission-console` branch.** Ensure all your final work occurs on top of this migration branch.

### 2. Remove Hardcoded State
- In `apps/web/components/Dashboard.tsx`, the mission state is currently driven by a `setTimeout` function that fabricates progress and hardcodes the initial query, stages, and evidence graph.
- **Action:** Rip out the `setTimeout` simulation. Use `backendAdapter.ts` to submit the actual `ExecuteRequest` to the Gateway.

### 3. Wire Up Live WebSockets
- Consume the P1 Gateway WebSocket stream (`/ws/v1/missions/{id}`). 
- Update the `RunTimeline`, `EvidencePanel`, and `MapCanvas` dynamically as real events arrive from the Agent orchestrator.

### 4. Connect Map Rendering to Live P4 Data
- Instead of showing static PNGs from `public/fixtures/assam-baseline-water.png`, configure MapLibre to pull live Cloud Optimized GeoTIFF (COG) tiles from the TiTiler integration managed by Kavin (P4).

### 5. Final Integration Testing
- Spin up the full `docker-compose.yml` stack included in your branch. Ensure the frontend can successfully submit a flood query, display the live agent reasoning, and render the final mapped output from the backend.
