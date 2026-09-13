"""Fixtures for the contract tests.

Deliberately self-contained, and deliberately a near-duplicate of two fixtures in
``ml/conftest.py``. The alternative -- one suite importing the other's conftest --
would make ``packages/`` depend on ``ml/``, and on ``ml``'s *tests* at that, which
is the dependency direction the contract convergence (ADR-0007 D17) exists to
remove. Twelve
duplicated lines is the cheaper of the two.

Everything here is synthetic: hand-built values whose properties can be computed
by hand. That is not the "mock data" this project bans -- see ml/conftest.py for
the distinction the project draws.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.contracts import (
    BackscatterScale,
    PassDirection,
    Polarization,
    Provider,
    RasterSpec,
    SceneRef,
)


@pytest.fixture
def scene_pre() -> SceneRef:
    """A pre-event Sentinel-1 scene reference."""
    return SceneRef(
        provider=Provider.ASF_HYP3,
        collection="sentinel-1-rtc",
        item_id="S1A_IW_20240801T003000_DVP_RTC10_G_gpuned_ABCD",
        acquired_at=datetime(2024, 8, 1, 0, 30, tzinfo=timezone.utc),
        platform="SENTINEL-1A",
        instrument="C-SAR",
        relative_orbit=63,
        pass_direction=PassDirection.DESCENDING,
        href="https://datapool.asf.alaska.edu/RTC/SA/pre.tif",
    )


@pytest.fixture
def scene_post() -> SceneRef:
    """A post-event scene from the same relative orbit and pass direction."""
    return SceneRef(
        provider=Provider.ASF_HYP3,
        collection="sentinel-1-rtc",
        item_id="S1A_IW_20240813T003000_DVP_RTC10_G_gpuned_EFGH",
        acquired_at=datetime(2024, 8, 13, 0, 30, tzinfo=timezone.utc),
        platform="SENTINEL-1A",
        instrument="C-SAR",
        relative_orbit=63,
        pass_direction=PassDirection.DESCENDING,
        href="https://datapool.asf.alaska.edu/RTC/SA/post.tif",
    )


@pytest.fixture
def utm_spec() -> RasterSpec:
    """A raster spec in a projected CRS with the model's expected band order."""
    return RasterSpec(
        band_order=(Polarization.VV, Polarization.VH),
        scale=BackscatterScale.DECIBEL,
        dtype="float32",
        crs="EPSG:32643",
        width=8,
        height=8,
        pixel_size_m=(10.0, 10.0),
        nodata=None,
    )
