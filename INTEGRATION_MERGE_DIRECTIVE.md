# Integration Branch Merge Directive

Date: 2026-09-24  
Target branch: `integration`

P1, P2, P3, P4, P5, and P6 owners must merge their feature branches into `integration` and integrate against the shared branch. Each team must resolve conflicts, update contracts where required, and attach test evidence to its pull request.

## Required merge sequence

1. P1: gateway, contracts, auth, mission events
2. P2: agent orchestration and event publication
3. P3: live model artifacts and inference runtime
4. P4: provider, raster, storage, and TiTiler runtime
5. P5: generated client, WebSocket UI, and live map
6. P6: Compose, secrets, observability, security, E2E, and release gate

## Integration rules

- Rebase or merge the latest `integration` before requesting review.
- Do not merge demo fixtures, hardcoded observations, or baseline results into the production path.
- Keep demo mode explicitly labelled and isolated.
- Add or update contract tests when an API or event schema changes.
- A green frontend build alone is insufficient; the full stack must pass the flagship browser workflow.
- No promotion to `main` until all six current-status PRDs have their acceptance criteria satisfied.

## Current release decision

**HOLD.** The current repository is suitable for integration-branch consolidation and continued development, but not for a live production release.
