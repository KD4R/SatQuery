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

`/` is the landing page, `/console` is the mission console.

With `NEXT_PUBLIC_DEMO_MODE=1` the whole flow runs with no backend: the console is
fed from `lib/fixtures/` and every panel carries a **DEMO FIXTURE** badge, with
`ENV: DEMO` in the telemetry bar. Set it to `0` to talk to a real gateway at
`NEXT_PUBLIC_GATEWAY_URL`.

## Checks

```bash
npm run typecheck    # tsc --noEmit
npm run test         # vitest — unit + the gateway route contract test
npm run build        # next build
npm run test:e2e     # playwright
```

## Layout

| Path | Holds |
|---|---|
| `app/` | Routes. `/` landing, `/console` mission console. |
| `components/shell/` | `MissionShell`, `TopTelemetryBar` |
| `components/console/` | Query panel, run timeline |
| `components/map/` | `MapWorkspace` — MapLibre, AOI draw/edit, layers |
| `components/observe/` | `BeforeAfterViewer` |
| `components/evidence/` | `IntelligencePanel` — change, confidence, WHY, sensors |
| `components/landing/` | `OrbitalGlobe` and the landing page |
| `components/system/` | Primitives, error boundary, failure states |
| `lib/api/` | Gateway client. See its README for why it is hand-written. |
| `lib/geo/` | AOI validation, coordinate and area formatting |
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
