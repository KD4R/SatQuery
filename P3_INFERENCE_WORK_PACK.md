# P3: ML & Inference Work Package (Srushti)

## Objective
Replace the "deterministic baseline" degraded mode with actual model weights and live raster processing logic. 

## Tasks

### 1. Procure and Load Real Model Artifacts
- The directory `infrastructure/models/` is currently empty.
- **Action:** Download, place, and properly version the required model weights (e.g., Optical, SAR flood segmentation models like `hand-only-v2`). Update `services/inference/registry.py` to actually load them into memory/GPU on startup.

### 2. Connect the Inference Pipeline
- `services/inference/implementation.py` currently explicitly states: "Starts with no model and no torch... runs the deterministic baseline and says so via degraded_from."
- **Action:** Modify the `/api/v1/inference/analyses` endpoint to pass the incoming `AssetRef` or raster URI to the loaded models. It must run actual semantic segmentation and generate the change polygon/masks.

### 3. Generate Genuine Output Metrics
- Calculate real measurements (e.g., `inundation_area_ha`) based on the output of your loaded models rather than hardcoded floats.
- Ensure the inference result successfully calculates and populates the `confidence` score based on the model's actual calibration metrics.

### 4. GPU/Worker Configuration
- If deploying to a GPU environment, ensure your Celery workers are correctly configured to allocate VRAM without OOM errors. Coordinate with Swarali (P6) to ensure the `docker-compose.yml` supports the required runtime capabilities.
