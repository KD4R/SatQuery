# P5 Frontend UX — Implementation Plan

**Engineer:** Swarali (Frontend UX) · **Branch:** `swarali` · **Status:** planning (no feature code written yet)

Basis for this plan: the PRD (`P5_SWARALI_AEI_PRD.md`) checked against what actually exists
in the repo after merging `feat/p5-mission-console` + `feat/p5-frontend-migration`.
Every claim below was verified in the tree on 2026-09-23.

---

## 0. Starting state (what the merge gave us)

| Capability | Status | Where |
|---|---|---|
| Mission-console shell (nav, telemetry bar, panels, design tokens) | ✅ exists | `components/shell/*`, `system/primitives.tsx`, `app/mission.css` |
| MapLibre map with layer toggles, AOI draw, comparison wipe | ✅ exists | `components/map/MapWorkspace.tsx` |
| Run timeline with demo script (9 stages, pinned dwell times) | ✅ exists | `console/MissionTimeline.tsx`, `lib/useMissionRun.ts` |
| Evidence panel (text-level "why" for flagged polygons) | ✅ exists (text only) | `evidence/IntelligencePanel.tsx` |
| WebSocket gateway `WS /ws/v1/missions/{id}` | ✅ exists | `services/gateway/routers/missions_ws.py` |
| TiTiler mounted in geo service (`/api/v1/tiles`) | ✅ exists | `services/geo/tiles.py` (P4-15) |
| Sensor-disagreement computation (SAR vs optical IoU, anomaly) | ✅ exists | `services/agent/evidence/disagreement.py` → `DisagreementReport` |
| `SENSOR_DISAGREEMENT` / `ACQUIRING_EVIDENCE` **events** | ❌ do not exist anywhere in the backend | — |
| React Flow, timeline slider, impact dashboard, WS client in web | ❌ not started | — |
| Token storage (A02) | ✅ module-scoped variable, never localStorage | `lib/api/gateway.ts`, asserted in e2e |
| CSP, X-Frame-Options, nosniff headers | ✅ (from migration) | `next.config.ts` |

Key implication: the PRD's WebSocket events are **not a wiring job, they are a contract job**.
The event names must be added to `packages/contracts/events.py`, emitted by the agent, and
published through the existing Redis pub/sub that `missions_ws.py` already bridges.

---

## 1. Milestone A — Evidence Graph / WHY Panel (build first)

The signature feature, and the one with the most existing data to lean on.

**Backend truth to render (verified):**
- Calibration-gated confidence: `services/inference/confidence.py` — a value may only be
  printed when a calibration justifies it; masks without one are rendered as
  "unavailable" today. The graph must honour that (node renders NOT AVAILABLE, never a fake %).
- Provenance fields: `src_chip_id`, `model_version`, `water_threshold` on inference responses.
- `has_role` ranking + tenant isolation on every route.

**Frontend work:**
1. `lib/evidence/graph.ts` — pure functions building a node/edge model from an insight +
   its provenance. Types mirror `EventEnvelope` payloads; unit-tested with vitest.
2. `components/evidence/EvidenceGraph.tsx` — React Flow (`@xyflow/react`) canvas,
   dynamically imported like MapWorkspace (`ssr: false`) to keep it off first paint.
   Node kinds: Insight → Confidence Gate (threshold + calibration state) → Model node
   (version) → Data nodes (T1/T2 chips, SAR/or optical). Clicking a node opens its detail.
3. Wire into `IntelligencePanel`: each flagged insight gets a "WHY" affordance that opens
   the graph in a slide-over. Keyboard reachable, Escape closes (match existing a11y bar).
4. XSS (A03): provenance strings are text nodes, never `dangerouslySetInnerHTML`. Audit
   rule: no new `dangerouslySetInnerHTML` outside the one theme bootstrap in `layout.tsx`.

**Demo/live split:** demo path builds the graph from fixture provenance; live path from
inference response fields. No fake fallback — the existing rule stands.

**Definition of done:** typecheck, eslint, vitest for graph builders; Playwright case
clicks WHY and asserts node labels + confidence gate; build stays < 180 kB first-load JS
for the console route (React Flow lazy-loaded).

---

## 2. Milestone B — Earth Time Machine UI

**Backend truth:** TiTiler is mounted (P4-15) but is fed COGs the pipeline produces per run.
There is **no multi-epoch archive endpoint yet** (Jan/Feb/Mar browsing needs one).

**Frontend work:**
1. `components/map/TimeMachine.tsx` — a slider control (Jan → Feb → Mar for the Assam
   demo scenario; generic over available epochs when live) with:
   - smooth crossfade between raster layers (two MapLibre raster layers, opacity ramp),
   - a change-mode that displays the change raster for the selected pair,
   - keyboard operable (arrows move epochs; ARIA slider role),
   - `prefers-reduced-motion` disables the crossfade.
2. `lib/map/timeLayers.ts` — layer-id scheme + style diffing so layer swaps do not
   flicker or drop the AOI source.
3. Integration point: `MapWorkspace.tsx` gains a `time` prop driven from the console.

**Backend asks (file as issues, do not block on):**
- `GET /api/v1/timeseries/{aoi}` listing available epochs per AOI (from P4 archive),
- TiTiler asset URLs served through the gateway (CSP `connect-src`/`img-src` already allow
  `self` + `data:`/`blob:` — keep tiles same-origin via the `/api/v1` rewrite).

**Definition of done:** Playwright drags the slider in demo mode and asserts the change
legend and epoch label swap; reduced-motion test; no console errors on rapid drags.

---

## 3. Milestone C — Real-time Agent UI (contract first, then UI)

**Step 1 — contracts (small PR, cross-team):** add to `packages/contracts/events.py`:
`AGENT_THOUGHT`, `ACQUIRING_EVIDENCE`, `SENSOR_DISAGREEMENT` event types with typed
payloads (`DisagreementReport` fields for the last one — it already has exactly the right
shape). Publish from the agent orchestrator where the disagreement analysis runs.
`missions_ws.py` needs no change: it already bridges Redis pub/sub → WS and re-verifies
token + tenant per connection.

**Step 2 — frontend:**
1. `lib/ws/useMissionEvents.ts` — WS client: token passed as `?token=` (the route's only
   supported mechanism; it is short-lived and never persisted, satisfying A02),
   exponential backoff reconnect, heartbeat, StrictMode-safe (AbortController-style
   cleanup like `useMissionRun`), and a hard rule: events only *add detail* to states the
   job API already reports (the no-fake-progress rule extends to the socket).
2. `components/console/AgentActivityToasts.tsx` — stacked, auto-expiring, non-intrusive
   toasts (`⚠ Optical and SAR sensors disagree on flood extent (IoU 0.42). Acquiring an
   additional radar observation…`), `aria-live="polite"`, pause-on-hover, max 3 visible.
   Toast text renders event fields as text (A03).
3. Timeline integration: `ACQUIRING_EVIDENCE` appends a detail line to the running stage
   in `MissionTimeline` rather than inventing a new stage.
4. Demo mode: the fixture script gains the two event moments so Playwright can assert
   toasts deterministically.

**Definition of done:** vitest for the reconnect/backoff state machine; Playwright asserts
the disagreement toast appears in demo; a live test with the gateway asserts auth failure
closes with policy-violation and the UI degrades to polling (no toast storm).

---

## 4. Milestone D — Infrastructure Impact Graph

**Backend truth:** PostGIS impact data is Kavin's (P4) deliverable; no impact endpoint
exists yet. Frontend defines the contract and ships against fixtures first.

**Frontend work:**
1. `lib/impact/model.ts` — hierarchical model: Hazard (flood) → Category (roads, hospitals,
   power) → Item (with exposure + confidence). Mirrors whatever the P4 impact query
   returns; fixtures carry the Assam scenario.
2. `components/impact/ImpactPanel.tsx` — sunburst/treemap-style breakdown with
   framer-motion expand/collapse (already a dependency), numbers animate on change,
   each node links back to the map (focuses the AOI) and to the Evidence Graph.
3. Console layout: becomes the third rail section, collapsible, lazy-loaded.

**Definition of done:** vitest for aggregation math (sums must equal the total — same
honesty rule as the timeline); Playwright expands nodes; matches design tokens.

---

## 5. Cross-cutting rules (apply to every milestone)

- **XSS (A03):** all agent/backend strings render as React text. No HTML injection
  anywhere. Add an eslint ban on `dangerouslySetInnerHTML` outside `layout.tsx`.
- **A02:** tokens stay in the module-scoped variable; WS reconnect re-reads it, never
  persists it. Tiles/API same-origin via the existing rewrite.
- **Performance:** every new heavy dep is `next/dynamic` + `ssr:false`; React Flow and the
  impact viz must not enter the landing/console critical path. Budget: console first-load
  JS stays ≤ 180 kB (currently 167 kB).
- **Honesty rules carry over:** degraded is a first-class state; no progress that was not
  reported; NOT AVAILABLE beats invention.
- **Testing ladder per milestone:** vitest (pure logic) → eslint → typecheck → build →
  Playwright in demo mode. CI keeps the e2e steps the merge restored.

## 6. Sequencing & asks

| Order | Milestone | Depends on | Backend ask |
|---|---|---|---|
| 1 | A. Evidence Graph | nothing (fixture provenance) | none |
| 2 | C. Agent UI step 1 (contracts) | agreement from agent owner | emit 3 event types |
| 3 | B. Time Machine | epochs endpoint is *nice-to-have* | timeseries endpoint (issue) |
| 4 | C. Agent UI step 2 (toasts) | C step 1 merged | — |
| 5 | D. Impact Graph | P4 impact query shape | impact endpoint (issue) |

Estimates: A ≈ 2–3 days, B ≈ 2 days + backend dependency, C ≈ 2 days (0.5 contract),
D ≈ 2 days. A and B can start in parallel; C-contracts should go out first because it
unblocks the agent team.
