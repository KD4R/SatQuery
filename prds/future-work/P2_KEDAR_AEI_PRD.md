# Autonomous Earth Investigator: P2 AI & Agent PRD

## Engineer: Kedar
**Role:** AI / Agent Engineer

---

## 1. Executive Summary
Your responsibility is the "brain" of the Autonomous Earth Investigator. You will upgrade the LangGraph orchestrator from a simple linear pipeline into a complex, reasoning, self-improving loop that can evaluate its own uncertainty and request more evidence.

## 2. End-to-End Implementation Guide

### A. Autonomous Mission Planner & Self-Improving Loop
Currently, the pipeline runs once and stops. You must introduce a **Confidence Gate**.
- **Action:** After the ML models (P3) return a result, the agent must evaluate the confidence score. If `confidence < 0.85` (or a dynamic threshold), the agent must *not* return the answer.
- Instead, the agent loops back, generates a new data acquisition request (e.g., "Requesting SAR data because Optical confidence is low due to cloud cover"), and waits for the new data before synthesizing the final answer.

### B. Multi-Sensor Disagreement Engine
If Optical says "Flooded (82%)" but SAR says "Not Flooded (41%)", the agent must not average the scores silently.
- **Action:** Create a `evaluate_sensor_consensus` node in LangGraph. If disagreement > X%, generate a `SENSOR_DISAGREEMENT` event. The agent must explicitly state the disagreement in its reasoning log, request a tie-breaker image, or present the uncertainty to the user.

### C. Natural Language to GIS ("Earth Sherlock")
Users will ask: "How much vegetation disappeared within 2 km of these roads?"
- **Action:** Equip the LLM agent with Tool Calling capabilities mapped to Kavin's (P4) PostGIS functions. The agent must parse the natural language, realize it needs a `buffer(roads, 2km)` and `intersect(buffer, vegetation_loss)`, and execute those tool calls autonomously to build the answer.

### D. Evidence Graph Provenance
Every claim the agent makes must have a traceable lineage. 
- **Action:** The agent must output an `EvidenceGraph` JSON object alongside its text answer, linking claims directly to the asset IDs and model inference IDs used to make them.

---

## 3. Delegation Prompt

Copy and paste this prompt to your coding agent or use it as your strict checklist:

```text
You are the P2 AI / Agent Engineer. Your goal is to upgrade the LangGraph orchestrator into a fully autonomous investigator with self-improving reasoning loops.

TECHNICAL TASKS:
1. Autonomous Mission Planner & Re-investigation Loop: Implement a Confidence Gate in the LangGraph. If the models return low confidence, the agent must autonomously define required sensors/dates and trigger a self-improving loop to acquire more evidence before answering the user.
2. Multi-Sensor Disagreement Engine: Build reasoning nodes that explicitly compare Optical, SAR, and Temporal results. Surface disagreements transparently as specific events, rather than silently failing or averaging them out.
3. Natural Language to GIS (Earth Sherlock): Upgrade the agent's Tool Calling abilities to translate natural language questions (e.g., "buildings within 500m of flood") into discrete GIS operations executed via the P4 geospatial tools.
4. Evidence Graph: Construct a JSON provenance tree for every final claim to power the frontend "WHY?" panel.

SECURITY & QUALITY (OWASP Top 10):
- Injection (A03): Heavily sanitize all LLM inputs and outputs, specifically ensuring that natural language parsed into GIS operations cannot be manipulated into destructive spatial queries (SQL injection).
- Server-Side Request Forgery (SSRF) (A10): When the agent dynamically requests new satellite assets, strictly whitelist the allowed provider endpoints.
- Write production-grade, secure code. Ensure the reasoning loop has a strict `MaxIter` limit so it cannot hit infinite recursion (resource exhaustion).
```
