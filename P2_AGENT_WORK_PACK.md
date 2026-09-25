# P2: Agent Orchestration Work Package (Kedar)

## Objective
Remove all hardcoded fallback scenes and test intercepts from the LangGraph orchestrator. Make the AI agent wait for and consume live data from the P3 (Inference) and P4 (Geospatial) services.

## Tasks

### 1. Remove Asset Acquisition Mocks
- In `services/agent/graph/orchestrator.py` (`acquire_data` node), the agent uses `stac_search` but has a deterministic fallback `_fallback_fn()` that returns `["S1A_IW_GRDH_1SDV_FALLBACK"]`.
- **Action:** Remove this fallback. If `stac_search` fails, the agent must either retry, alter its plan to use a different sensor, or cleanly report an acquisition failure to the user.

### 2. Remove Inference Mock Intercepts
- In `services/agent/graph/orchestrator.py` (`analyze_data` node), there is a block that checks `CELERY_TASK_ALWAYS_EAGER` and forcefully returns a hardcoded result: `{"degraded_from": "baseline", "measurements": [{"name": "inundation_area_ha", "value": 14250.0, "unit": "ha"}]}`.
- **Action:** Remove this mock intercept. The agent must `await client.post("/api/v1/inference/analyses")` and process the actual live results returned by Srushti's P3 service.

### 3. Wire Up Live Confidence Metrics
- The `gate_check` node hardcodes some confidence heuristics. 
- **Action:** Ensure `evaluate_confidence_gate()` takes the real metadata and outputs from P3/P4. If confidence is below the threshold, implement the logic to return explicit uncertainty to the user rather than proceeding.

### 4. End-to-End Synthesis
- Ensure `synthesizer.py` correctly handles empty or failed `EvidenceGraph` states now that the mocks are gone. It must gracefully report what went wrong to the user if no flood evidence could be generated.
