"""Shared fixtures.

Note on test data
-----------------
Everything here is **synthetic**: hand-built arrays with properties we can compute
by hand. That is deliberate and is *not* the "mock data" this project bans.

The distinction the project draws:

* **Synthetic test data** never reaches a user, exists only under ``tests/``, and
  is how you verify that Otsu finds a threshold you calculated yourself. Required.
* **Mock product data** is a fabricated value on a code path a user can reach.
  Banned.

The package boundary enforces it: nothing under ``src/`` may import from ``tests``,
and CI fails the build if it does.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import numpy.typing as npt
import pytest

from ml.contracts.scene import (
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


@pytest.fixture
def bimodal_change() -> npt.NDArray[np.float32]:
    """A change image with two well-separated modes and a known separation point.

    Half the pixels sit near -8 dB (a strong backscatter decrease -- flooding) and
    half near +1 dB (no change). Otsu should return a threshold comfortably between
    the two clusters, which is what ``test_otsu_*`` asserts.

    A fixed seed keeps the test deterministic; the assertions are on the interval
    the threshold must fall in, not on an exact value, so they do not encode
    floating-point noise.
    """
    rng = np.random.default_rng(seed=20260911)
    flooded = rng.normal(loc=-8.0, scale=0.5, size=2048)
    unchanged = rng.normal(loc=1.0, scale=0.5, size=2048)
    result: npt.NDArray[np.float32] = np.concatenate([flooded, unchanged]).astype(np.float32)
    return result
