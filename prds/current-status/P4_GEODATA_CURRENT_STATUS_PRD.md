# P4 Geospatial & EO Data — Current Status PRD

Status: **PARTIAL / BLOCKED for release**  
Owner: P4 geodata team  
Merge target: `integration`

## Implemented

- Provider interfaces, Bhoonidhi adapter structure, STAC normalization, raster validation, CRS/clip/COG helpers, worker/recovery logic, S3/MinIO configuration, and TiTiler configuration exist.

## Remaining before sign-off

- Validate live Bhoonidhi/Earth Search authentication and catalog search with deployment secrets.
- Remove production fixture fallback behavior; upstream failure must retry or return a clear failure.
- Download and stage real assets into S3/MinIO.
- Verify validation → UTM reprojection → AOI clip → COG → storage → TiTiler URL on a real scene.
- Return complete AssetRef metadata, including download URI, to P2/P3.
- Add provider outage, quality rejection, and real-raster acceptance tests.

## Evidence

The current agent path can return fallback observations, and the live provider/raster path has not been validated in a running stack.

## Acceptance criteria

A real AOI/date query returns a quality-approved scene and a retrievable COG/TiTiler layer, or a typed failure with no fabricated observation.

## Required action

Merge the P4 feature branch into `integration` after P1/P2 contract alignment and attach evidence from a real provider run.
