"""Fixes on the live (Planetary Computer) inference path.

* sentinel-1-rtc is linear power, so it is declared POWER and converted to dB;
* the baseline path persists its mask and polygons (it used to return no refs);
* an AOI polygon limits what is measured to the polygon, not its bbox;
* the Azure allowlist names storage accounts instead of all of *.blob.core.windows.net;
* the AOI window read from a remote COG is capped.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform as warp_transform

from ml.io.preflight import PreflightError
from packages.contracts import BackscatterScale, SceneRef
from services.inference.artifacts import LocalArtifactSink
from services.inference.registry import ModelRegistry
from services.inference.scale import declared_scale_for
from services.inference.service import AnalysisService
from services.inference.sources import LocalRasterSource
from services.inference.validation import validate_href

pytestmark = pytest.mark.unit

CRS = "EPSG:32646"  # UTM 46N (Assam)
ORIGIN = (700_000.0, 2_920_000.0)
PX = 10.0
N = 200


def _scene(
    provider="planetary_computer", collection="sentinel-1-rtc", href="scene.tif"
) -> SceneRef:
    return SceneRef(
        provider=provider,
        collection=collection,
        item_id="S1A_TEST",
        acquired_at=datetime(2024, 7, 4, tzinfo=timezone.utc),
        platform="SENTINEL-1A",
        instrument="C-SAR",
        relative_orbit=12,
        pass_direction="ASCENDING",
        href=href,
    )


def _write_linear_power_scene(path: Path) -> None:
    """Left half open water (-23 dB), right half land (-9 dB), in LINEAR power."""
    rng = np.random.default_rng(7)
    db = np.where(np.arange(N)[None, :] < N // 2, -23.0, -9.0) + rng.normal(0, 0.8, (N, N))
    vv = (10 ** (db / 10)).astype(np.float32)
    vh = (10 ** ((db - 6) / 10)).astype(np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=N,
        height=N,
        count=2,
        dtype="float32",
        crs=CRS,
        transform=from_origin(*ORIGIN, PX, PX),
    ) as dst:
        dst.write(vv, 1)
        dst.write(vh, 2)
        dst.set_band_description(1, "VV")
        dst.set_band_description(2, "VH")


def _lonlat(x, y):
    lon, lat = warp_transform(CRS, "EPSG:4326", [x], [y])
    return [lon[0], lat[0]]


@pytest.fixture
def service(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    _write_linear_power_scene(root / "scene.tif")
    sink = LocalArtifactSink(tmp_path / "store")
    svc = AnalysisService(
        registry=ModelRegistry(tmp_path / "no-models"),
        source=LocalRasterSource(root),
        code_version="test",
        artifacts=sink,
    )
    return svc, tmp_path / "store"


def test_declared_scale_table():
    assert declared_scale_for(_scene()) is BackscatterScale.POWER
    assert (
        declared_scale_for(_scene(provider="sen1floods11", collection="S1Hand"))
        is BackscatterScale.DECIBEL
    )
    assert declared_scale_for(None) is BackscatterScale.DECIBEL


def test_linear_rtc_is_thresholded_in_db_and_persisted(service):
    svc, store = service
    out = svc.analyse(
        scene=_scene(), scene_href="scene.tif", trace_id="11111111-1111-4111-8111-111111111111"
    )
    assert out.outcome == "analysed", getattr(out, "explanation", None)
    # Threshold lands between the two classes in dB, not on linear 0..1 values.
    otsu = next(c for c in out.caveats if c.startswith("single-date Otsu"))
    threshold = float(otsu.split("threshold ")[1].split(" dB")[0])
    assert -21.0 < threshold < -11.0
    # Half the 2 km x 2 km window is water: ~200 ha (reprojection trims edges).
    assert 170 <= float(out.measurements[0].value) <= 215
    # The baseline now persists what it measured.
    assert out.geometry_ref and out.geometry_ref.endswith("water_extent.geojson")
    assert (store / out.geometry_ref).is_file()
    assert out.degraded_from is not None
    assert out.caveats[0].startswith("produced by ")


def test_aoi_polygon_limits_the_measurement(service):
    svc, _ = service
    # A polygon over the left quarter of the grid (all water): x in [0, 50) px.
    x0, x1 = ORIGIN[0] + 2 * PX, ORIGIN[0] + 48 * PX
    y0, y1 = ORIGIN[1] - 2 * PX, ORIGIN[1] - 198 * PX
    ring = [_lonlat(x0, y0), _lonlat(x1, y0), _lonlat(x1, y1), _lonlat(x0, y1), _lonlat(x0, y0)]
    out = svc.analyse(
        scene=_scene(),
        scene_href="scene.tif",
        aoi_geometry={"type": "Polygon", "coordinates": [ring]},
        trace_id="22222222-2222-4222-8222-222222222222",
    )
    assert out.outcome == "analysed"
    area = float(out.measurements[0].value)
    # 46 x 196 px of water = ~90 ha; the whole-window answer would be ~200 ha.
    assert 70 <= area <= 100
    assert any("inside the AOI polygon" in c for c in out.caveats)


def test_aoi_polygon_outside_scene_abstains(service):
    svc, _ = service
    far = {"type": "Polygon", "coordinates": [[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]]}
    out = svc.analyse(
        scene=_scene(),
        scene_href="scene.tif",
        aoi_geometry=far,
        trace_id="33333333-3333-4333-8333-333333333333",
    )
    assert out.outcome == "abstained"
    assert "AOI polygon" in out.explanation


def test_azure_allowlist_is_account_specific(monkeypatch):
    validate_href(
        "https://sentinel1euwestrtc.blob.core.windows.net/sentinel1-grd-rtc/a/vv.tif?sig=x"
    )
    with pytest.raises(PreflightError):
        validate_href("https://attacker.blob.core.windows.net/exfil")
    monkeypatch.setenv("SATQUERY_EXTRA_ASSET_HOSTS", "newaccount.blob.core.windows.net")
    validate_href("https://newaccount.blob.core.windows.net/x.tif")


def test_remote_window_pixel_cap(monkeypatch, tmp_path):
    from services.inference import sources

    path = tmp_path / "big.tif"
    _write_linear_power_scene(path)
    monkeypatch.setattr(sources, "MAX_WINDOW_PIXELS", 1_000)
    monkeypatch.setattr(sources, "validate_href", lambda href: None)
    src = sources.RemoteRasterSource(tmp_path / "cache")
    lon0, lat0 = _lonlat(ORIGIN[0], ORIGIN[1] - N * PX)
    lon1, lat1 = _lonlat(ORIGIN[0] + N * PX, ORIGIN[1])
    with pytest.raises(PreflightError, match="pixel limit"):
        src._crop_remote_pair(str(path), str(path), [lon0, lat0, lon1, lat1])
