# ADR-0001: Python Monorepo with Flat Package Layout

**Status:** Accepted  
**Date:** 2026-09-11  
**Deciders:** Platform Engineering Team  

---

## Context

SatQuery AI is a multi-service backend platform (Gateway, Mission, AI Agents, EO-Data, Geo, etc.).  
We needed to decide whether to organise these services in a **monorepo** (single Git repository) or a
**polyrepo** (one repository per service).

## Decision

We use a **single Git monorepo** with a flat package layout:

```
SatQuery-1/
  packages/          # Shared libraries (auth, observability, shared client, contracts)
  services/          # Deployable services (gateway, mission, agent, …)
  tests/             # Cross-cutting integration and contract test suites
  docs/              # Architecture docs, ADRs, OpenAPI specs
  scripts/           # CI and developer tooling
```

Shared code lives in `packages/` and is imported directly via `PYTHONPATH=.` — no private PyPI publishing is required during P1.

## Consequences

### Positive
- **Atomic commits** — a single PR can change both a shared library and all services that consume it, keeping them in sync.
- **Unified CI** — one `.github/workflows/ci.yml` gate enforces linting, typing, tests, and security across every component.
- **Code reuse without ceremony** — `from packages.auth import require_role` just works; no package versioning overhead.
- **Simplified onboarding** — one `git clone`, one `pip install -r requirements.txt`, and the full stack is runnable locally.

### Negative / Mitigations
- **Build times grow with codebase** — mitigated by `pytest -m unit|integration|contract` markers to parallelise job stages.
- **Merge conflicts on shared modules** — mitigated by module ownership conventions and a `CODEOWNERS` file.
- **Single blast radius** — a bad commit could break all services simultaneously; mitigated by mandatory PR reviews and the CI gate.

## Alternatives Considered

| Option | Reason Rejected |
|---|---|
| Polyrepo (one repo per service) | Complex cross-service dependency management; duplicate CI boilerplate; no atomic cross-service changes |
| Monorepo + Bazel | Too much Bazel learning curve for a P1 sprint; can be adopted later as the team scales |
