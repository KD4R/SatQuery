# ADR-0007: AI Agent State, Tool Registry, and LangGraph Orchestration Architecture

**Status:** Accepted  
**Date:** 2026-09-12  
**Deciders:** P2 Agent Engineering Team, Platform Architecture (P1)  

---

## Context

SatQuery AI's flagship natural-language flood mission copilot requires an autonomous agent system capable of parsing natural language user intents, orchestrating multi-sensor observation searches (Sentinel-1 SAR, Sentinel-2 Optical), arbitrating sensors based on cloud coverage and mission constraints, constructing an auditable Evidence Graph, enforcing confidence gating, and generating evidence-only explanations with provenance metadata.

Core requirements include:
- Deterministic orchestration with LangGraph state machine.
- Strict prevention of LLM hallucinations: the LLM functions as a coordinator/synthesizer, never as a source of truth.
- Zero-trust input sanitization with regex pattern defense against prompt injections.
- Permission-aware tool execution with strict per-mission token and call budgets.
- Automated fallback and recovery policies for Bhoonidhi STAC timeouts, inference OOM, and sensor disagreement.

## Decision

We implement a dedicated, modular agent subsystem under `services/agent/` and root packages (`graph/`, `nodes/`, `tools/`, `evidence/`, `security/`, `evals/agent/`):

### Core Architecture Components

1. **MissionState & Schema Serialization (`graph/state.py`, `packages/contracts/agent.py`)**:
   - Strongly-typed Pydantic DTOs for `MissionState`, `SensorDecision`, `EvidenceNode`, `ConfidenceReport`, and `ErrorResponse`.
   - Explicit propagation of correlation identifiers: `trace_id`, `mission_id`, `run_id`, `job_id`, `organization_id`.

2. **Security & Prompt Defense (`security/`)**:
   - `InputSanitizer`: Strips malicious jailbreak phrases, control characters, and logs blocked attacks (`prompt_injection_block_total`).
   - `ToolBudgetTracker`: Thread-safe tracking of tool calls and tokens per mission to prevent denial-of-wallet and runaway execution loops.
   - `AuditLogger`: Audit logs all tool invocations with status and latency.

3. **LangGraph Pipeline Nodes (`nodes/`, `graph/`)**:
   - `IntentExtractor`: Parses natural language intent into structured parameters (disaster type, temporal bounds, AOI, sensors).
   - `TemporalPlanner`: Computes pre-event baseline and post-event event windows with buffer intervals.
   - `SensorArbitrator`: Arbitrates between Optical and SAR based on cloud cover, temporal proximity, and all-weather requirements.
   - `EvidenceGraphBuilder`: Assembles directed acyclic evidence graphs linking raw assets, inference masks, and derived flood statistics.
   - `ConfidenceGate`: Evaluates overall confidence against configurable threshold (default 0.75), routing low-confidence or conflicting data to clarification/acquisition.
   - `DisagreementAnalyzer`: Identifies spatial and semantic disagreement between optical and SAR flood delineations.
   - `EvidenceSynthesizer`: Synthesizes final actionable natural language briefings using strictly grounded evidence from the evidence graph.
   - `ResilienceManager`: Implements bounded retry and deterministic fallback to pinned golden fixtures on external STAC or inference worker failures.

4. **Autonomous Execution Loop (`graph/acquisition_loop.py`)**:
   - Iterative evidence loop that automatically triggers complementary SAR or Optical acquisitions when initial confidence is below threshold.

5. **Release Hardening & Pinned Demo Profile (`services/agent/demo_profile.py`)**:
   - Provides offline reproducible demo runs against pinned Bihar flood STAC fixtures (`fixtures/pinned_flood_mission.json`).

## OWASP Alignment

- **LLM01: Prompt Injection**: Regex-based defense and control string stripping via `InputSanitizer`.
- **LLM02: Sensitive Information Disclosure**: Sanitization of auth tokens and PII prior to model invocation or audit logging.
- **LLM07: System Prompt Leakage**: Input validation blocks prompt extraction attempts.
- **LLM10: Unbounded Consumption**: Strict limits on tool calls and total tokens via `ToolBudgetTracker`.

## Consequences

### Positive
- Subsystem is completely independent, observable via OpenTelemetry and Prometheus, and contract-conforming.
- Hallucinations are prevented structurally through strict evidence grounding.
- Full offline reproducibility for demos and deterministic unit/contract testing.

### Negative / Mitigations
- In-memory budget tracker will be backed by distributed Redis in multi-instance deployments.
