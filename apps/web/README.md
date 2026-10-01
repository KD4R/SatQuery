# SatQuery — Web (P5)

Map-first mission console for SatQuery AI. Next.js 15 · React 19 · MapLibre ·
Framer Motion · TypeScript.

## Run it locally

```bash
cd apps/web
npm install          # required — node_modules is not portable between machines
cp .env.example .env.local
echo "NEXT_PUBLIC_DEMO_MODE=1" >> .env.local   # deterministic demo, no backend needed
npm run dev          # http://localhost:3000
```

`/` is the landing page, `/dashboard` is the mission console (`/console` and the
other old paths redirect there; see `lib/nav.ts`).

With `NEXT_PUBLIC_DEMO_MODE=1` the whole flow runs with no backend: the console is
fed from `lib/fixtures/` and every panel carries a **DEMO FIXTURE** badge, with
`ENV: DEMO` in the telemetry bar. Set it to `0` to talk to a real gateway at
`NEXT_PUBLIC_GATEWAY_URL`.

### Live mode against the local stack

```bash
docker compose up -d --build            # from the repo root: gateway, agent, inference, …
cd apps/web
GATEWAY_ORIGIN=http://localhost:8000 npm run dev
```

Without Docker (less disk and memory): run only the gateway, agent and inference
with uvicorn. No Postgres or Redis is needed for a live run.

```bash
python3 -m venv .venv && source .venv/bin/activate   # repo root
pip install -r requirements.txt
./scripts/run-local-backend.sh                        # leave running
# second terminal
cd apps/web && npm install && GATEWAY_ORIGIN=http://localhost:8000 npm run dev
```

The console signs itself in through the gateway's development login
(`POST /api/v1/auth/dev-token`, enabled by compose with `ENVIRONMENT=development`
and `SATQUERY_DEV_LOGIN=1`). The token stays in memory; a reload mints a new one.
Without that route the console asks for a token on the Admin page.

The rail walks through the run with a step bar (**Where → When → Ask → Run →
Result**); each step is clickable and jumps to its control. A live run needs an
area: in **Where**, search a place and **Use this place**, or draw a
**Rectangle** / **Polygon** on the map. **When** is optional: Auto (the last 90
days, widened once to a year — the result says which), 7 / 30 / 90 days, or a
custom range. Every figure in the rail and under the map
comes from the agent's run state (`lib/live/result.ts`); the water outline is the
inference service's stored extent for that run.

`npm run dev` and `npm run build` first copy MapLibre's worker into
`public/vendor/maplibre/` (`scripts/copy-maplibre-worker.mjs`). Without it no
GeoJSON layer renders (AOI, water, change polygons) because maplibre-gl v6 cannot
find its worker inside a bundled chunk.

## Checks

```bash
npm run typecheck    # tsc --noEmit
npm run test         # vitest — unit + the gateway route contract test
npm run build        # next build
npm run test:e2e     # playwright — the deterministic demo
npm run test:e2e:live  # playwright — live mode against a stubbed gateway (recorded runs)
```

## Layout

| Path | Holds |
|---|---|
| `app/` | Routes. `/` landing, `/dashboard` mission console, `/dashboard/*` sections. |
| `components/Dashboard.tsx` | The mission console: map-first; rail with query, result, steps, plan |
| `components/dash/` | Live result, failure, running and idle cards; live intelligence detail |
| `components/console/` | Agent-activity toasts |
| `components/map/` | `MapWorkspace` — MapLibre, AOI draw/edit, layers |
| `components/observe/` | `BeforeAfterViewer` |
| `components/evidence/` | `IntelligencePanel` — change, confidence, WHY, sensors |
| `components/landing/` | `OrbitalGlobe` and the landing page |
| `components/system/` | Primitives, error boundary, failure states |
| `lib/api/` | Gateway client. See its README for why it is hand-written. |
| `lib/geo/` | AOI validation, coordinate and area formatting, place search |
| `lib/live/` | Live run adapter: steps per agent node, MissionState → view, dev sign-in, water extent |
| `lib/model/` | View models for surfaces the gateway does not yet expose |
| `lib/fixtures/` | The demo scenario. The only source of non-backend data. |

## Two rules the code enforces

**Demo data is never passed off as backend data.** `Sourced<T>` carries its origin
to the component that renders it, every fixture-fed panel shows a badge, and a
failed live call renders a failure state — it never falls back to a fixture,
because doing that silently is fabricating success.

**A value that is not known says so.** The `NotAvailable` component renders
`NOT AVAILABLE` with the reason. `grep -rn "NotAvailable" components` is the list
of places the system admits a gap; that list is what makes the WHY panel worth
reading.

## Demo fixture provenance

`public/fixtures/*.png` are renderings of Sen1Floods11 hand-labelled chip
`India_533192` — a real Sentinel-1 acquisition over the Brahmaputra floodplain near
Nagaon, Assam (93.873–93.919 E, 26.768–26.814 N). Observed water 35.8% of analysed
pixels, permanent water 3.3%, new water 33.3%, 46% of the chip inside the swath.
Details and the reason each null field is null are in `lib/fixtures/assam.ts`.
