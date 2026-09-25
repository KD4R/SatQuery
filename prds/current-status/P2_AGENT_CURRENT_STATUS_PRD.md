# P2 Agent Orchestration — Current Status PRD

Status: **PARTIAL / BLOCKED for release**  
Owner: P2 agent team  
Merge target: `integration`

## Implemented

- LangGraph planning, sensor arbitration, tool registry/executor, evidence graph, confidence gate, synthesis, sanitization, and bounded recovery are present.
- Failure states are represented and synthesis has empty-evidence handling.

## Remaining before sign-off

- Remove the eager-mode hardcoded STAC observations and all production acquisition fallbacks.
- Pass real provider asset references and raster URIs into P3; do not reconstruct fake S3 paths.
- Remove forced baseline selection from the live path.
- Use P3/P4 confidence, metadata, disagreement, and quality outputs in the gate.
- Implement explicit sensor-disagreement and low-confidence re-investigation behavior.
- Persist and publish granular agent events consumed by P1/P5.

## Evidence

The P2 schema compatibility test currently ends in `FAILED` because no observations are acquired. The acquisition tool still contains an eager-mode hardcoded fallback.

## Acceptance criteria

With live P4 and P3 services available, a natural-language mission completes using real assets, records provenance, abstains or re-investigates below threshold, and emits events through the P1 WebSocket.

## Required action

Merge the P2 feature branch into `integration` after P1 contract alignment and include a live-provider integration test result.
