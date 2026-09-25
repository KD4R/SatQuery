# Delegation Prompts for P1–P5 Engineers

Here are the 5 ready-to-copy prompts to send to your team or their coding agents. They are designed to enforce the correct git workflow, prioritize security, and remove all remaining mocks to achieve end-to-end integration.

***

## P1: Backend & Gateway (Siddharth)
**Prompt:**
```text
You are the P1 Backend and Gateway Engineer. Your goal is to finalize the API boundaries and ensure real-time state propagation across the system. 

WORKFLOW INSTRUCTIONS:
1. Check out the `feat/p5-frontend-migration` branch (this is the unified integration branch containing the latest backend schemas and frontend generated clients).
2. Create a new branch from it named `p1-integration`.
3. Do your work on this branch. We will eventually merge all `p1` to `p5` branches back into `main` simultaneously to achieve full end-to-end functionality.

TECHNICAL TASKS:
1. Solidify the API Gateway proxying rules in `services/gateway/routers/proxy.py` to ensure all generated OpenAPI requests from the P5 frontend route perfectly to the P2, P3, and P4 services.
2. Fix the WebSocket implementation in `services/gateway/routers/missions_ws.py`. Remove the mock sequence fallback and connect it to the live Redis/Celery streams used by the P2 Agent so the frontend receives real-time progress.
3. Support the frontend (P5) in integrating the generated API client if schema mismatches occur. You will coordinate with Swarali for this.

SECURITY & QUALITY (OWASP Top 10):
- Ensure all endpoints hit by the P5 UI require and rigidly validate JWT tokens (`jwt.py`), preventing Broken Access Control (A01).
- Ensure Service-to-Service (S2S) tokens are strictly passed down the trace.
- Write production-grade, secure, and end-to-end integrable code. No more stubs. Your output must be fully deployable.
```

***

## P2: AI / Agent Engineer (Kedar)
**Prompt:**
```text
You are the P2 AI / Agent Engineer. Your goal is to remove all hardcoded test intercepts from the LangGraph orchestrator and force the agent to consume live data.

WORKFLOW INSTRUCTIONS:
1. Check out the `feat/p5-frontend-migration` branch (this is the unified integration branch containing the latest schemas and infrastructure).
2. Create a new branch from it named `p2-integration`.
3. Do your work on this branch. We will eventually merge all `p1` to `p5` branches back into `main` simultaneously to achieve full end-to-end functionality.

TECHNICAL TASKS:
1. In `services/agent/graph/orchestrator.py`, locate the `acquire_data` node. Remove the deterministic `_fallback_fn` that returns `["S1A_IW_GRDH_1SDV_FALLBACK"]`. The agent must wait for real asset retrieval from P4 or handle failures cleanly.
2. In the `analyze_data` node, remove the `CELERY_TASK_ALWAYS_EAGER` intercept that returns a hardcoded 14250.0 ha result. Make the agent await the real `client.post("/api/v1/inference/analyses")` call to P3.
3. Connect `evaluate_confidence_gate()` and the synthesizer to the actual real-time outputs from the P3/P4 pipeline rather than static placeholders.

SECURITY & QUALITY (OWASP Top 10):
- Maintain rigorous prompt sanitization (`sanitize_prompt`) to prevent Injection (A03).
- Strictly enforce `ToolBudget` limits to prevent resource exhaustion/client-side DoS.
- Write production-grade, secure, and end-to-end integrable code. No more stubs or fixtures in the production path. Your output must be fully deployable.
```

***

## P3: ML / Computer Vision Engineer (Srushti)
**Prompt:**
```text
You are the P3 ML / Computer Vision Engineer. Your goal is to replace the "deterministic baseline" mock mode with actual model weight execution.

WORKFLOW INSTRUCTIONS:
1. Check out the `feat/p5-frontend-migration` branch (this is the unified integration branch containing the latest schemas and infrastructure).
2. Create a new branch from it named `p3-integration`.
3. Do your work on this branch. We will eventually merge all `p1` to `p5` branches back into `main` simultaneously to achieve full end-to-end functionality.

TECHNICAL TASKS:
1. Procure the actual Optical and SAR model weights (e.g., `hand-only-v2`) and configure `services/inference/registry.py` to load them into memory/GPU on startup instead of skipping initialization.
2. Modify `services/inference/implementation.py` (specifically the `/api/v1/inference/analyses` endpoint) to pass the incoming raster paths to the loaded models and perform real semantic segmentation.
3. Calculate real output metrics (e.g., actual `inundation_area_ha`) and confidence calibration scores based on the live model outputs rather than returning fixed floats.

SECURITY & QUALITY (OWASP Top 10):
- Ensure model inputs (AssetRefs/raster file paths) are rigidly validated to prevent Path Traversal or SSRF vulnerabilities (A04/A10).
- Handle memory limits and potential OOM errors gracefully.
- Write production-grade, secure, and end-to-end integrable code. No more degraded baselines in the production path. Your output must be fully deployable.
```

***

## P4: Geospatial & Data Engineer (Kavin)
**Prompt:**
```text
You are the P4 Geospatial & Data Engineer. Your goal is to establish live, robust connections to Earth Observation catalogs and remove fixture fallbacks.

WORKFLOW INSTRUCTIONS:
1. Check out the `feat/p5-frontend-migration` branch (this is the unified integration branch containing the latest schemas and infrastructure).
2. Create a new branch from it named `p4-integration`.
3. Do your work on this branch. We will eventually merge all `p1` to `p5` branches back into `main` simultaneously to achieve full end-to-end functionality.

TECHNICAL TASKS:
1. In `services/geo/implementation.py`, remove or bypass the `FixtureFallbackManager` in the production execution path. The system must query Bhoonidhi/Earth Search live, and fail or retry cleanly if upstream providers are down.
2. Verify that `BhoonidhiAdapter` correctly authenticates, searches, and retrieves live EO assets.
3. Ensure the Celery async worker (`process_geo_job`) perfectly executes raster validation, CRS normalization, PostGIS AOI clipping, and COG generation on live data, and that these assets are accessible via TiTiler.

SECURITY & QUALITY (OWASP Top 10):
- Validate all incoming GeoJSON and raster bytes extensively to prevent Security Misconfiguration and Injection (A03/A05). Do not process malformed rasters.
- Ensure all provider secrets are injected securely via environment variables and never logged (A09).
- Write production-grade, secure, and end-to-end integrable code. No more pinned JSON fixtures in the production path. Your output must be fully deployable.
```

***

## P5: Frontend UX Engineer (Swarali)
**Prompt:**
```text
You are the P5 Frontend UX Engineer. Your goal is to finalize the migration to the generated OpenAPI client, strip all `setTimeout` mocks, and wire the UI directly into the live backend.

WORKFLOW INSTRUCTIONS:
1. Check out the `feat/p5-frontend-migration` branch. **This branch is critical** because it contains the generated OpenAPI client, `backendAdapter.ts`, and Docker changes that `feat/p5-mission-console` lacks.
2. Create a new branch from it named `p5-integration`.
3. Do your work on this branch. We will eventually merge all `p1` to `p5` branches back into `main` simultaneously to achieve full end-to-end functionality.

TECHNICAL TASKS:
1. In `apps/web/components/Dashboard.tsx`, rip out the `setTimeout` simulation that fabricates mission progress and hardcoded evidence graphs. 
2. Use the newly generated `backendAdapter.ts` to submit actual `ExecuteRequest` payloads to the P1 Gateway.
3. Consume the Gateway WebSocket stream (`/ws/v1/missions/{id}`) to dynamically update the `RunTimeline`, `EvidencePanel`, and `MapCanvas` as real events arrive from the backend.
4. Configure MapLibre to pull live Cloud Optimized GeoTIFF (COG) tiles from the TiTiler server instead of rendering static PNGs.

SECURITY & QUALITY (OWASP Top 10):
- Ensure all API calls securely attach the required authentication headers. Never store long-lived sensitive tokens in unsafe `localStorage` locations (A07).
- Sanitize any HTML or evidence strings returned from the backend before rendering them to prevent Cross-Site Scripting (XSS) (A03).
- Write production-grade, secure, and end-to-end integrable code. No more hardcoded states. Your output must be fully deployable.
```

***

# Phase 2: Autonomous Earth Investigator Prompts

The following prompts delegate the "Autonomous Earth Investigator" capabilities to the team. Ensure that all implementations adhere to production-grade security and the OWASP Top 10 standards.

***

## P1: Backend & Gateway (Siddharth) - Phase 2
**Prompt:**
```text
You are the P1 Backend and Gateway Engineer. Your goal is to architect the new API surfaces to support the "Autonomous Earth Investigator" features.

TECHNICAL TASKS:
1. Support New Endpoints: Create robust API routes for the new Evidence Graph, temporal query capabilities, Infrastructure Impact Graph, and the Autonomous Mission Planner.
2. Real-time Streams for Agents: Expand the WebSocket streams to handle new event types such as "SENSOR DISAGREEMENT" events, autonomous re-investigation loops, and continuous monitoring updates.
3. Mission Memory State: Design and implement the persistence layer for "Mission Memory" so the agent can recall previous monitoring tasks and states.

SECURITY & QUALITY (OWASP Top 10):
- Broken Access Control (A01): Enforce strict tenant isolation on all new mission planning and memory endpoints.
- Security Logging and Monitoring Failures (A09): Implement comprehensive audit logs for all autonomous actions taken by the agent (e.g., acquiring new evidence).
- Write production-grade, secure code. All API payloads must be strictly validated.
```

***

## P2: AI / Agent Engineer (Kedar) - Phase 2
**Prompt:**
```text
You are the P2 AI / Agent Engineer. Your goal is to upgrade the LangGraph orchestrator into a fully autonomous investigator.

TECHNICAL TASKS:
1. Autonomous Mission Planner & Re-investigation Loop: Implement logic where the agent autonomously defines required sensors/dates. If the Confidence Gate fails or sensors conflict, trigger a self-improving loop to acquire more evidence before answering.
2. Multi-Sensor Disagreement Engine: Build the reasoning nodes that explicitly compare Optical, SAR, and Temporal results and surface disagreements transparently instead of silently failing.
3. Natural Language to GIS (Earth Sherlock): Upgrade the agent's ability to translate natural language questions ("How much vegetation disappeared within 2 km of these roads?") into discrete GIS tool calls.

SECURITY & QUALITY (OWASP Top 10):
- Injection (A03): Heavily sanitize all LLM inputs and outputs, specifically ensuring that natural language parsed into GIS operations cannot be manipulated into destructive spatial queries or SQL injections.
- Server-Side Request Forgery (SSRF) (A10): When the agent dynamically requests new satellite assets, strictly whitelist the allowed provider endpoints.
- Write production-grade, secure code. Ensure the reasoning loop cannot hit infinite recursion (resource exhaustion).
```

***

## P3: ML / Computer Vision Engineer (Srushti) - Phase 2
**Prompt:**
```text
You are the P3 ML / Computer Vision Engineer. Your goal is to expand the system's inferencing capabilities beyond basic flood detection.

TECHNICAL TASKS:
1. Expanded Feature Models: Integrate and deploy models to detect Buildings, Roads, and Vegetation (incorporating foundation models like Prithvi where scalable).
2. Building Status Engine: Output multi-state classifications (e.g., New construction, Demolition, Flood affected) rather than simple binary detections.
3. Uncertainty & Confidence Scoring: Provide calibrated confidence scores for all inferences. This is critical to power the Sensor Disagreement Engine and trigger autonomous re-investigation.

SECURITY & QUALITY (OWASP Top 10):
- Vulnerable and Outdated Components (A06): Ensure all ML libraries, PyTorch, and CUDA dependencies are updated and free of known CVEs.
- Insecure Design (A04): Architect the inference pipeline to securely handle multi-model loading without memory leaks or race conditions.
- Write production-grade, secure code. Ensure model endpoints cannot be abused to cause Denial of Service via excessively large raster inputs.
```

***

## P4: Geospatial & Data Engineer (Kavin) - Phase 2
**Prompt:**
```text
You are the P4 Geospatial & Data Engineer. Your goal is to build the advanced GIS and temporal data foundations.

TECHNICAL TASKS:
1. Earth Time Machine: Implement robust temporal asset retrieval from STAC catalogs, enabling the system to query historical states for a given AOI across multiple dates.
2. Infrastructure Impact Graph & Road Accessibility: Build the PostGIS/spatial operations (buffer, intersect, difference) to calculate relationships (e.g., which buildings intersect flood zones). Implement a road graph for accessibility routing.
3. Data Quality Intelligence: Actively evaluate incoming STAC assets for cloud cover, missing bands, and geometry quality, rejecting unsuitable images before they reach the ML models.

SECURITY & QUALITY (OWASP Top 10):
- Injection (A03): Parameterize all PostGIS queries. Never concatenate strings for spatial operations.
- Security Misconfiguration (A05): Ensure the STAC and TiTiler infrastructure is hardened, with restricted CORS and unexposed management ports.
- Write production-grade, secure code. Ensure heavy GIS graph recalculations are resource-limited.
```

***

## P5: Frontend UX Engineer (Swarali) - Phase 2
**Prompt:**
```text
You are the P5 Frontend UX Engineer. Your goal is to build the visual interface for the Earth Investigator.

TECHNICAL TASKS:
1. Earth Time Machine UI: Build a dynamic timeline slider that smoothly transitions the MapCanvas between different historical states and displays temporal change maps.
2. Evidence Graph / WHY Panel: Implement a traceable, interactive node graph that allows users to click on an AI claim and visually walk backward through the evidence and confidence scores.
3. Complex Impact Visualizations: Design the "Sensor Disagreement" alerts, the Cross-Modal Consensus Map (color-coded agreement layers), and the Infrastructure Impact dashboard.

SECURITY & QUALITY (OWASP Top 10):
- Cross-Site Scripting (XSS) (A03): Rigorously sanitize all dynamic text, explanations, and event narratives generated by the agent before rendering them in the DOM.
- Cryptographic Failures (A02): Ensure all map tiles and API requests are served exclusively over HTTPS with secure cookies.
- Write production-grade, secure code. Deliver a premium, highly responsive UI that handles large amounts of map data without freezing.
```
