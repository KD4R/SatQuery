# P3 Inference — Current Status PRD

Status: **DEGRADED / BLOCKED for release**  
Owner: P3 inference team  
Merge target: `integration`

## Implemented

- Inference API, schemas, validation, registry, baseline pipeline, provenance fields, and model-selection contracts exist.
- Service can serve a labelled deterministic baseline when no learned model is available.

## Remaining before sign-off

- Supply and version real SAR/optical model weights; the current model directory contains no checkpoint.
- Load and verify the selected model at startup.
- Process real AssetRef/raster input rather than baseline-only execution.
- Generate masks/polygons, measured area, and calibrated confidence from model output.
- Define CPU/GPU worker resources and prevent OOM under the deployment profile.
- Add live inference acceptance tests with a real model artifact.

## Evidence

`infrastructure/models/` contains a manifest but no model weights. The service documentation explicitly permits degradation to the deterministic baseline.

## Acceptance criteria

An analysis request against a staged raster returns a non-null model identity, genuine measurements, calibrated confidence, provenance, and a persisted output URI; baseline use is explicit and approved only for non-production demo mode.

## Required action

Merge the P3 feature branch into `integration` only after the artifact checksum, loading, inference, and resource tests pass.
