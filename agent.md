# agent.md — Operating Guide for AI Coding Agents

You are working on **SatQuery AI** — a natural-language satellite-intelligence
platform. A user types a question ("Show flood-affected areas around Nagaon,
Assam"), an LLM agent plans it, arbitrates sensors, acquires Earth-observation
data, runs flood-extent inference, and returns an evidence-backed answer with
provenance. This file tells you how to work here without breaking the things
that make the project trustworthy.

---

## 1. Golden rules (read before writing any code)

1. **Honesty over polish.** A value the backend did not supply renders as
   `NOT AVAILABLE` with a reason — never as `0`, never as a guessed number, and
   never as a fixture value in live mode. A stage that analysed 46% of the AOI
   is `DEGRADED`, not green. Fake progress for real work is forbidden: the live
   run timeline has exactly the states the backend reports and nothing else.
2. **Fixtures are deterministic and only via the barrel.** Import demo data
   exclusively from `apps/web/lib/fixtures/index.ts`. Pinned epoch, no
   `Date.now()` in demo paths. The demo must be byte-identical on every run so
   Playwright can assert on it.
3. **Exactly one module may read `NEXT_PUBLIC_DEMO_MODE`.** That is
   `apps/web/lib/api/source.ts` (`demoModeEnabled()`). An isolation test
   enforces this. Never branch on the env var anywhere else.
4. **The browser talks only to the gateway.** `apps/web/lib/api/gateway.ts` is
   the only module that calls `fetch`; it refuses absolute URLs (SSRF guard).
   The bearer token is a module-scoped variable — never localStorage or
   sessionStorage. `organization_id` is derived from the verified token at the
   gateway, never sent by the client.
5. **Envelopes pass through verbatim.** The gateway WS bridge forwards
   agent-event envelopes untouched; do not reshape them in the proxy.
6. **No ML number outside `reports/evaluation.md`.** That file is generated,
   fingerprinted, and CI-checked. If a figure about the model does not appear
   there, you may not quote it in a slide, README, or test.
7. **Never claim a verification you did not run.** "Tests pass" means you ran
   them in this session and saw the output.

---

## 2. Repository map

```
apps/web/            P5 frontend — Next.js 15 App Router, TypeScript
services/gateway/    P1 API gateway / BFF — auth, proxy, WS bridge, rate limits
services/mission/    P1 mission & AOI lifecycle, job registry (Postgres)
services/agent/      P2 LangGraph agent — plan, arbitrate, acquire, analyze
services/inference/  P3 model serving
services/eo-data/    P4 EO ingestion (Bhoonidhi/STAC)
services/geo/        P4 geospatial processing
ml/                  model training & evaluation (PyTorch)
packages/            contracts, auth (JWT/RBAC), shared client
infrastructure/      docker compose, observability, release
docs/                ADRs, API refs, security policies
prds/                phase PRDs (P1..P6 + master)
reports/             generated evaluation report (accuracy gate)
tests/               contract, integration, e2e, security, performance, chaos
```

The three-zone console lives in `apps/web/components/`:
`shell/MissionShell.tsx` (query rail | map | intel rail, drawers below 1100px),
`shell/TopTelemetryBar.tsx` (tab chrome + breadcrumb + ENV chip),
`console/` (query panel, timeline), `evidence/IntelligencePanel.tsx`,
`map/MapWorkspace.tsx` + `map/TimeMachine.tsx`, `impact/InfrastructureImpact.tsx`.

---

## 3. Services and ports (local stack)

| Container | Port | Notes |
|---|---|---|
| satquery-api (gateway) | **8000** | every browser call goes here |
| satquery-mission | 8001 | missions, jobs |
| satquery-agent | 8002 | agent execute / runs |
| satquery-inference | 8003 | |
| satquery-web (live) | **3002** | compose service `web` |
| satquery-web-demo | **3010** | `NEXT_PUBLIC_DEMO_MODE=1` build, fixtures |
| satquery-postgres | 5433 | host port shifted to avoid collisions |
| satquery-redis | 6379 | run state + pub/sub |
| grafana / prometheus | 3001 / 9090 | |
| titiler / minio | 8081 / 9000-9001 | |

Compose file: `infrastructure/docker/docker-compose.yml`. Note: the host's
`.env` (gitignored) carries `POSTGRES_PORT=5433`, `WEB_PORT=3002` — other
projects own 5432/3000 on this machine.

---

## 4. How the live path works (memorise this)

1. Browser `POST /api/v1/agent/execute` (Dashboard copilot) or
   `POST /missions/{id}/runs` (mission flow) → gateway → **202 + job id**.
2. The agent service creates run state with `AgentOrchestrator.create_run`,
   which persists to **Redis `agent:run:{job_id}`** (24 h TTL) behind a
   process-local cache. Any process can read it: the API process, a Celery
   worker, the poller.
3. The graph streams in a daemon thread (`worker._stream_run`), publishing
   status + Phase-C event envelopes to Redis channel
   `mission:{mission_id}:status`.
4. The gateway WS (`/ws/v1/missions/{id}?token=`) subscribes to that channel:
   envelope-shaped messages pass **verbatim**; plain status dicts become
   `status_update` events; terminal status sends `done` and closes.
5. The mission service's background task polls
   `GET /api/v1/agent/runs/{agent_job_id}` (up to 180 s) and drives **both job
   and mission** to terminal status — a job stuck `running` forever is a lie.
6. The web client: `useMissionRun` polls the **agent run endpoint** (not
   `GET /jobs/{id}` — that is the mission service's registry and does not know
   agent job ids), with a bounded 15 s 404 grace window
   (`RUN_NOT_FOUND` = "not registered yet"). The console's WS is keyed by
   `run.missionId ?? run.jobId`.

Runs honestly **fail locally** when no real EO observations exist ("No
observations found to analyze."). That is correct behaviour, not a bug.

---

## 5. Commands

```bash
# frontend
npm run typecheck --prefix apps/web
npm run lint --prefix apps/web
npm run test --prefix apps/web                    # vitest
npm run build --prefix apps/web                   # keep First-Load JS ≤ 180 kB
cd apps/web && npx playwright test                # e2e (starts its own server)

# python (gateway/contracts/agent-events)
python -m pytest tests/integration/test_p1_05_p1_08_gateway.py \
  packages/contracts/tests services/agent/events -q

# orchestrator unit tests (host python env is broken — run in container)
docker exec satquery-api python -m pytest tests/unit/test_p2_04_async_execute.py -q

# containers
docker compose -f infrastructure/docker/docker-compose.yml build web
docker compose -f infrastructure/docker/docker-compose.yml up -d --force-recreate web
docker build --build-arg NEXT_PUBLIC_DEMO_MODE=1 -t satquery-web:demo \
  -f apps/web/Dockerfile apps/web
docker rm -f satquery-web-demo && docker run -d --name satquery-web-demo \
  --network docker_satquery -p 3010:3000 satquery-web:demo

# dev token (HS256, 8 h) — minted inside the api container, cached on host
docker exec satquery-api python -c "
import os,time;from jose import jwt;now=int(time.time())
print(jwt.encode({'sub':'dev-analyst','org_id':'org-demo','roles':['operator'],
'iss':'satquery-dev','aud':'satquery-dev','iat':now,'exp':now+8*3600},
os.environ['AUTH_SECRET_KEY'],algorithm='HS256'))" > /tmp/satquery_dev_token

# WS exercise client (streams a mission's channel to stdout)
docker exec -d satquery-api sh -c \
  "SATQUERY_TOKEN='$(cat /tmp/satquery_dev_token)' python /tmp/ws_exercise.py <mission_id> 180"
```

⚠️ `services/eo-data` contains a hyphen — do **not** `pip install -e` it from
the host env; the local Python environment is known-broken for it. Run python
tests that need the full stack inside containers.

---

## 6. Debugging playbook (hard-won)

- **401 everywhere in the browser** → the token died. It is memory-only by
  design (a full page load signs you out). Re-paste it on `/admin` (live mode).
- **`TOKEN_EXPIRED`** → mint a fresh token (§5). Expiry is 8 h.
- **Agent run 404 from the mission poller or dashboard** → the run state must
  be in Redis. Check `redis-cli GET agent:run:{job_id}`. If the poller hits
  `GET /jobs/{agent_job_id}` it will always 404 — wrong registry.
- **Stale chunks / MIME "text/html" module errors after a rebuild** → the
  browser cached old HTML. Cache-bust (`?v=2`) or open a fresh tab; the
  Freebuff preview browser also needs a *new tab* (not reload) to clear some
  renderer states.
- **Console UI looks like drawers at desktop size** → viewport < 1100 px;
  `MissionShell` collapses rails into MISSION/INTELLIGENCE drawers. Widen.
- **Compose recreated the old image** → compose derives its own image name for
  services with a `build:` block; `docker tag` alone does nothing. Use
  `docker compose build <svc>` then `up -d --force-recreate <svc>`.
- **Playwright strict-mode duplicates** (e.g. landing shows `0.435` twice) →
  use `.first()`.
- **otel/`otel-collector` DNS warnings in agent logs** → telemetry export
  noise, unrelated to run correctness. Filter them before reading logs.
- **`409 MISSION_ALREADY_RUNNING`** → reset the mission with
  `PATCH /missions/{id}` `{"status":"failed"}` before resubmitting.

---

## 7. Definition of done

A change here is done when **all** of these are green *and you ran them*:

- [ ] `npm run typecheck`, `lint`, `vitest` (60), `build` (≤180 kB),
      Playwright (20) — for web changes
- [ ] pytest gateway/contracts/events (92) — for API changes
- [ ] Demo container :3010 and live :3002 rebuilt and smoke-tested (HTTP 200 +
      one real interaction) when the UI changed
- [ ] No new `NEXT_PUBLIC_DEMO_MODE` reader; fixtures only via the barrel
- [ ] No new number without a source in `reports/evaluation.md` (ML) or the
      backend payload (UI); absence renders `NOT AVAILABLE` with a reason
- [ ] Playwright selectors still strict-mode-safe; a11y affordances kept
      (aria-live status, Escape exits every mode, focus visible)
- [ ] Commit message explains **why**; heredoc format with the Codebuff footer

## 8. Do not touch without explicit instruction

- `infrastructure/docker/.env` (local secrets, gitignored)
- The isolation test and the single-demo-mode-reader rule
- The gateway's verbatim envelope passthrough
- `reports/evaluation.md` (regenerate it; never hand-edit)
- Production compose vs the root `docker-compose.yml` minio/s3 divergence —
  known, intentional; do not "fix" casually
