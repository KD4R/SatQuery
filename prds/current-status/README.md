# SatQuery AI — Current Release Status PRDs

Status date: 2026-09-24  
Target branch: `integration`

These six PRDs record the current implementation state, release blockers, acceptance criteria, and branch-integration instructions for P1–P6. They are an as-is release audit, not a claim that the application is production-ready.

## Overall status

**Release status: NOT READY for a live end-to-end release.**

The repository builds at the frontend level and has broad unit/contract coverage, but the flagship workflow is still blocked by missing inference artifacts, fixture/fallback paths, incomplete live provider wiring, WebSocket integration gaps, and the absence of a verified full-stack Docker run.

## Merge order

1. P1 gateway and shared contracts
2. P2 agent orchestration
3. P3 inference artifacts and runtime
4. P4 EO/provider and geospatial pipeline
5. P5 frontend integration
6. P6 infrastructure, security, observability, and release verification

All owners must merge their feature branches into `integration`, resolve conflicts there, and run the acceptance checks in their PRD. No branch should be merged directly to `main` until the integration checklist is green.
