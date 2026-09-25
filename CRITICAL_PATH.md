# SatQuery AI - End-to-End Critical Path Audit

## Real vs Mock Path Analysis

### 1. Natural language query -> Gateway -> Mission
- **Caller:** Frontend UI (Next.js)
- **Endpoint/Function:** Gateway API `/api/v1/missions`
- **Request Schema:** `Canonical request/DTO`
- **Response Schema:** `MissionState`
- **Auth:** OIDC JWT (HS256 S2S token or RS256 prod token)
- **Status:** **MOCKED at UI Layer**. The `Dashboard.tsx` uses `setTimeout` to simulate query processing. It does not actually call the Gateway. Gateway and Mission backend services exist and have tests, but are not connected to the frontend.

### 2. Mission -> Agent
- **Caller:** Mission Service
- **Endpoint/Function:** `services/agent/graph/orchestrator.py` `create_run`
- **Status:** **PARTIAL**. Agent endpoints exist but the demo explicitly uses a pinned fallback `services/agent/demo_profile.py` `run_pinned_demo_profile`.

### 3. Agent -> EO Provider -> Observation -> AssetRef
- **Caller:** Agent `acquire_data` node
- **Function:** `executor.execute_tool("stac_search")`
- **Status:** **MOCKED / DEGRADED**. The execution catches failures and hardcodes `["S1A_IW_GRDH_1SDV_FALLBACK"]`. A `FixtureFallbackManager` is present in `services/geo/implementation.py` to bypass live provider API calls.

### 4. Geo processing -> Inference
- **Caller:** Agent `analyze_data` node
- **Endpoint/Function:** `client.post("/api/v1/inference/analyses")`
- **Status:** **MOCKED**. Explicitly intercepts the async call if `CELERY_TASK_ALWAYS_EAGER` is set and returns a hardcoded dictionary with `inundation_area_ha`. The actual Inference Service explicitly starts with "no model and no torch" and falls back to a deterministic baseline.

### 5. Inference -> Evidence -> Confidence -> Decision
- **Caller:** Agent `gate_check` node
- **Function:** `EvidenceGraphBuilder`, `evaluate_confidence_gate`
- **Status:** **REAL BUT GROUNDED ON MOCK DATA**. The builder and confidence gate execute logic, but they are fed the hardcoded/fallback `inundation_area_ha` and `confidence` from earlier mocks.

### 6. Synthesis -> Report
- **Caller:** Agent `synthesize` node
- **Function:** `synthesize_evidence_output`
- **Status:** **REAL**. It accurately synthesizes a report based *strictly* on the `EvidenceGraph` using the measurements provided. It does not invent facts (Data/AI Safety passes), but the inputs it receives are mocked.

### 7. WebSocket -> P5 Map/UI
- **Caller:** Gateway
- **Endpoint/Function:** `/ws/v1/missions/{id}`
- **Status:** **MOCKED**. The frontend relies on a `setTimeout` function with hardcoded `stages` and `evidence` lists. The WebSocket integration is implemented in the backend (with Redis mock fallbacks) but is not consumed by the UI.

## Summary

The entire end-to-end flagship workflow is **severely broken** at the integration layer. While many backend microservices (P1-P4) have robust unit tests and skeleton implementations, the critical paths are bypassed using deterministic fixtures, fallbacks, and `setTimeout` delays in the frontend. 

The application cannot execute a real end-to-end scenario dynamically.
