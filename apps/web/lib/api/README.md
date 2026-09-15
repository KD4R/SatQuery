# `apps/web/lib/api/` — gateway access layer (P5-02)

## Why this client is hand-written

`docs/openapi/gateway.json` types every request and response body as `"schema": {}`.
The gateway is a transparent proxy, so its document describes **routes and auth and
nothing else**. Running codegen against it is what produced the committed client in
`packages/contracts/generated/ts/`, which contains exactly one model — `HealthStatus` —
and is therefore unusable for building a UI.

The real payload shapes are published by the two services behind the proxy:

| Spec | Supplies |
|---|---|
| `docs/openapi/mission.json` | `MissionResponse`, `JobStatusResponse`, `AOIResponse`, … |
| `docs/openapi/agent.json` | `PlanResponse`, `MissionState`, `ConfidenceResponse`, … |

So `types.ts` transcribes those, and each interface carries the spec and schema name
it came from.

## What keeps it honest

`routes.ts` is the single declaration of every path the browser may call, and
`__tests__/routes.contract.test.ts` asserts that it and `gateway.json` describe the
same set. A route added, renamed or removed on either side fails the test. That check
is the part doing the work that codegen would otherwise do.

The DTOs are not covered by that test — nothing machine-checkable exists to compare
them against while the gateway stays untyped. **When the gateway starts declaring real
schemas, delete `types.ts` and generate.** That is the intended end state; this is the
bridge to it.

## Updating types by hand

1. `python scripts/export_openapi.py` to refresh `docs/openapi/*.json`.
2. Diff `mission.json` / `agent.json` against the `@see` comment on each interface.
3. Update `types.ts`; run `npx tsc --noEmit`.

## Rules enforced in code

- `gateway.ts` is the only module that calls `fetch`. Absolute URLs are refused.
- The access token is a module variable. Never `localStorage` (PRD P5-15).
- `organization_id` is never sent by the client; the backend derives it from the token.
- Bounded timeout, at most two retries, 5xx and transport faults only.
- A failed call throws `GatewayError` with `trace_id`. It never falls back to a
  fixture — doing that silently would be fabricating success, which the PRD forbids.
