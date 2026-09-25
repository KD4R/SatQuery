# Autonomous Earth Investigator: P4 Geospatial & Data PRD

## Engineer: Kavin
**Role:** Geospatial & Data Engineer

---

## 1. Executive Summary
Your responsibility is to build the robust temporal data retrieval system and the advanced PostGIS operational logic. You provide the actual GIS computations that turn the ML pixel detections into physical impact metrics (The Infrastructure Impact Graph).

## 2. End-to-End Implementation Guide

### A. Earth Time Machine (Temporal Data)
The system needs to look backward in time smoothly.
- **Action:** Upgrade the STAC catalog retrieval (`BhoonidhiAdapter` / Earth Search) to handle complex temporal queries. When the frontend requests a timeline, you must rapidly discover and return a time-series stack of Cloud Optimized GeoTIFFs (COGs) for the given AOI.

### B. Data Quality Intelligence
Garbage in, garbage out. The agent shouldn't waste compute on 100% cloudy images.
- **Action:** Actively evaluate STAC item metadata. Reject images with excessive cloud cover, missing bands, or poor geometry *before* they are sent to P3 for ML inference. Report this quality rejection back to the agent so it knows to search for a different date.

### C. Infrastructure Impact Graph (PostGIS)
The AI agent will ask you for spatial relationships.
- **Action:** Write PostGIS functions to compute intersections. When P3 detects a flood polygon, you must intersect it with OSM building footprints and road networks. 
- Return JSON graphs like: `{ "flood_zone_1": { "affected_buildings": 42, "disrupted_roads": 8 } }`. 

### D. Road Accessibility Intelligence
- **Action:** Implement network routing logic (e.g., using pgRouting). If a road segment intersects a flood polygon, dynamically recalculate access to critical infrastructure (like hospitals) and return alternative route distances.

---

## 3. Delegation Prompt

Copy and paste this prompt to your coding agent or use it as your strict checklist:

```text
You are the P4 Geospatial & Data Engineer. Your goal is to build the advanced GIS, PostGIS impact graphs, and temporal data foundations for the Autonomous Earth Investigator.

TECHNICAL TASKS:
1. Earth Time Machine: Implement robust temporal asset retrieval from STAC catalogs, enabling the system to query and stack historical states for a given AOI across multiple dates.
2. Infrastructure Impact Graph & Road Accessibility: Build the PostGIS spatial operations (`ST_Buffer`, `ST_Intersects`, `ST_Difference`) to calculate relationships (e.g., which buildings intersect flood zones). Implement a road network graph to calculate accessibility and disrupted routes.
3. Data Quality Intelligence: Actively evaluate incoming STAC assets via metadata (cloud cover, missing bands, geometry quality) and reject unsuitable images before they reach the ML models, saving compute.

SECURITY & QUALITY (OWASP Top 10):
- Injection (A03): Heavily parameterize all PostGIS queries. Never concatenate strings for spatial operations, especially when inputs originate from the LLM agent.
- Security Misconfiguration (A05): Ensure the STAC and TiTiler infrastructure is hardened, with restricted CORS and unexposed management ports.
- Write production-grade, secure code. Ensure heavy GIS graph recalculations are resource-limited to prevent DoS.
```
