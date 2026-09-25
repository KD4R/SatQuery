# P4: Geospatial & Data Work Package (Kavin)

## Objective
Remove test fixtures and establish live, robust connections to Earth Observation catalogs (Bhoonidhi/STAC). Ensure the raster pipeline successfully normalizes and clips real data.

## Tasks

### 1. Remove Fixture Fallbacks
- `services/geo/implementation.py` currently utilizes a `FixtureFallbackManager` to return pinned JSON files (`data/fixtures/`) when live provider calls fail.
- **Action:** Remove or strictly bypass the `FixtureFallbackManager` in the production path. The system must actually query Bhoonidhi or Earth Search and fail cleanly (or retry) if the upstream provider is down.

### 2. Stabilize Bhoonidhi API Integration
- Verify that `packages.providers.bhoonidhi.BhoonidhiAdapter` is actually capable of hitting the live API, authenticating, searching the catalog, and securely retrieving/downloading the asset.
- Coordinate with Siddharth (P1) and Swarali (P6) to securely inject any required API keys or secrets via environment variables.

### 3. Validate Live Raster Pipeline
- Test the Celery `process_geo_job` async worker with real assets. 
- Ensure that the pipeline correctly performs:
  1. Raster validation
  2. CRS normalization (UTM reprojection)
  3. AOI clipping using PostGIS
  4. COG (Cloud Optimized GeoTIFF) generation.
- Ensure the generated COG is saved to the internal S3/MinIO storage and a valid URI is returned to the Agent/Inference modules.

### 4. TiTiler & Map Output
- Ensure the generated rasters are properly exposed via TiTiler for the P5 frontend to render on the MapLibre canvas.
