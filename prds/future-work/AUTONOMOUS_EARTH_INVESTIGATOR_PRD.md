# SatQuery AI: Autonomous Earth Investigator PRD

## Vision
SatQuery AI is evolving from a standard satellite image analysis tool into an **"Autonomous Earth Investigator"**. It acts as an agentic system that decides what evidence it needs, observes the planet across sensors and time, explains what changed, and keeps watching. 

Instead of a simple `Image -> Classification` pipeline, the workflow is:
**Question → Evidence → Analysis → Explanation → Decision → Report → Monitoring**

## Core Flagship Features

### 1. Autonomous Mission Planner
- **Concept:** Users task the agent rather than executing one-off queries. For example: *"Monitor this industrial corridor for unauthorized expansion."*
- **Capabilities:** The agent autonomously defines the Area of Interest (AOI), monitoring frequency, required sensors, types of analysis, and alert thresholds. It continues persistent monitoring in the background.

### 2. Earth Time Machine
- **Concept:** Temporal semantic change detection and reconstruction.
- **Capabilities:** A timeline UI that reconstructs and visualizes land cover, buildings, roads, vegetation, and water over time. It generates temporal change maps directly addressing queries like *"Show me what changed here since January."*

### 3. Multi-Sensor Disagreement Engine
- **Concept:** Transparent handling of conflicting multimodal data.
- **Capabilities:** The system cross-checks Optical, SAR, and Temporal data. If Optical suggests "flooded" but SAR says "not flooded", the system flags a **SENSOR DISAGREEMENT** and autonomously triggers an evidence acquisition loop to resolve the conflict.

### 4. Comprehensive Infrastructure Models
- **Concept:** Extending beyond basic flood detection to a full suite of Earth objects.
- **Capabilities:** Implement and fuse specialized models (or foundation models) for Buildings, Roads, Vegetation, and Flood extent to power subsequent GIS analysis and the Building Status Engine.

### 5. Infrastructure Impact Graph
- **Concept:** Moving from pixels to decision intelligence.
- **Capabilities:** Intersects detected changes with spatial infrastructure to generate a relationship graph. For example: *Flood Zone → affects 42 buildings, 8 roads → blocks hospital access.*

### 6. Evidence Graph / WHY Panel
- **Concept:** Traceable, explainable AI.
- **Capabilities:** Users can click on any claim (e.g., "Change detected") and walk backward through the evidence tree (Confidence → SAR overlap → Before/After images). It explicitly displays provenance.

### 7. Autonomous Monitoring & Re-investigation (Self-Improving Loop)
- **Concept:** The system decides when evidence is insufficient before making a final claim.
- **Capabilities:** If prediction confidence is low or sensors disagree, the agent autonomously requests more data (new dates, alternative sensors) before finalizing the report. 

## The Flagship Demo Flow
**User:** *"Analyze the latest flood impact in Guntur, compare it with the previous observation, identify affected buildings and roads, determine whether sensor evidence agrees, explain the evidence, and create a monitoring mission."*

**System Flow:**
USER QUERY → MISSION PLANNER → DATA AGENT → OPTICAL + SAR → TEMPORAL ENGINE → SENSOR CONSENSUS → EVIDENCE GRAPH → CONFIDENCE GATE → IMPACT GRAPH → REPORT → PERSISTENT MONITORING

The system demonstrates true agentic reasoning by stating: *"Evidence is insufficient around the western boundary. I requested an additional SAR observation before finalizing the result."*
