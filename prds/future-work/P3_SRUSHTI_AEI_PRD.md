# Autonomous Earth Investigator: P3 ML & Computer Vision PRD

## Engineer: Srushti
**Role:** ML / Computer Vision Engineer

---

## 1. Executive Summary
Your responsibility is to upgrade the system's "eyes". Basic binary flood detection is no longer sufficient. You must provide a comprehensive, multi-class, confidence-calibrated understanding of the Earth's surface to power the agent's infrastructure impact graphs and disagreement engines.

## 2. End-to-End Implementation Guide

### A. Expanded Feature Models (Beyond Floods)
The Impact Graph requires knowing what is actually on the ground.
- **Action:** Integrate and deploy semantic segmentation models capable of detecting: Buildings, Roads, Vegetation, and Surface Water/Floods. 
- You should strongly consider utilizing Geospatial Foundation Models (e.g., NASA Prithvi) to handle multiple EO tasks with a single backbone rather than loading 10 separate heavy models into VRAM.

### B. Building Status Engine & Change Detection
We don't just need to know a building exists; we need to know its *state*.
- **Action:** Implement temporal change detection. By comparing $T_1$ and $T_2$ inferences, output statuses like: `New Construction`, `Demolition`, `Flood Affected`, `No Change`. 

### C. Uncertainty & Calibrated Confidence Scoring
This is the most critical feature for the autonomous agent. The agent (P2) relies entirely on your confidence scores to decide whether to fetch more data.
- **Action:** Models must return calibrated uncertainty scores (e.g., a pixel-wise confidence heatmap or an aggregate classification confidence). Do not just return `Label: Building`. You must return `Label: Building, Confidence: 0.62`. 
- If the image is heavily clouded or noisy, the model should confidently output a *low* confidence score for the semantic classes, triggering the agent's self-improvement loop.

---

## 3. Delegation Prompt

Copy and paste this prompt to your coding agent or use it as your strict checklist:

```text
You are the P3 ML / Computer Vision Engineer. Your goal is to expand the system's inferencing capabilities to power the "Autonomous Earth Investigator" impact graphs and disagreement engines.

TECHNICAL TASKS:
1. Expanded Feature Models: Integrate and deploy segmentation models to detect Buildings, Roads, Vegetation, and Water. Utilize Geospatial Foundation Models (e.g., Prithvi) where scalable to optimize VRAM.
2. Building Status Engine: Output multi-state temporal classifications (e.g., "New construction", "Demolition", "Flood affected") rather than simple binary detections by comparing temporal rasters.
3. Uncertainty & Confidence Scoring: Provide calibrated confidence/uncertainty scores for all inferences. This is critical: the AI Agent relies on these exact scores to power the Sensor Disagreement Engine and trigger autonomous re-investigation loops. 

SECURITY & QUALITY (OWASP Top 10):
- Vulnerable and Outdated Components (A06): Ensure all ML libraries, PyTorch, and CUDA dependencies are updated and free of known CVEs.
- Insecure Design (A04): Architect the inference pipeline to securely handle multi-model loading without memory leaks, OOM crashes, or race conditions.
- Write production-grade, secure code. Ensure model endpoints cannot be abused to cause Denial of Service (DoS) via excessively large raster inputs.
```
