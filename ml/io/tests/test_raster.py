"""Tests for the raster reader and the deterministic baseline.

Every GeoTIFF here is written by the test with rasterio, from a synthetic array,
into ``tmp_path``. That is deliberate on two counts.

It is a *real* GeoTIFF -- a real GDAL round-trip, a real CRS, a real affine
transform -- so the reader is exercised against the format rather than against a
mock of it. And it is generated in-process rather than committed, so no fixture
asset exists that a product code path could ever load. Synthetic arrays under
tests are necessary; a fixture file that could stand in for a measurement is the
thing this package refuses.

The Sen1Floods11 chips are not used here. They are not in the repository, they are
not available to CI, and an offline suite that silently skips when they are absent
is a suite that reports green while testing nothing. Scoring against them is the
job of ``ml/scripts/evaluate_baseline.py``, which fails loudly when they are
missing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from ml.contracts.scene import BackscatterScale, Polarization, Provider, SceneRef
from ml.io.raster import RasterReadError, read_raster, reproject_to_area_safe_crs

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def write_tif(
    path: Path,
    data: np.ndarray,
    *,
    crs: str = "EPSG:32643",
    descriptions: tuple[str, ...] | None = ("VV", "VH"),
    pixel_size: float = 10.0,
    origin: tuple[float, float] = (500000.0, 1000000.0),
    nodata: float | None = None,
) -> Path:
    """Write a real GeoTIFF and return its path."""
    bands, height, width = data.shape
    transform = from_origin(origin[0], origin[1], pixel_size, pixel_size)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=bands,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as sink:
        sink.write(data.astype(np.float32))
        if descriptions is not None:
            for index, description in enumerate(descriptions, start=1):
                sink.set_band_description(index, description)
    return path


def bimodal_scene(water_rows: int = 20, size: int = 64, seed: int = 0) -> np.ndarray:
    """A two-band scene with a genuinely separable dark region.

    Land near -8 dB, water near -20 dB, with speckle. Separable on purpose: the
    tests below are about the plumbing, and a scene the threshold cannot split
    would fail for the wrong reason.
    """
    rng = np.random.default_rng(seed)
    vv = rng.normal(-8.0, 1.0, (size, size))
    vv[:water_rows, :] = rng.normal(-20.0, 1.0, (water_rows, size))
    vh = vv - 6.0
    return np.stack([vv, vh])


def a_scene_ref() -> SceneRef:
    return SceneRef(
        provider=Provider.ASF_HYP3,
        collection="sentinel-1-rtc",
        item_id="TEST_0001",
        acquired_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        platform="Sentinel-1A",
        instrument="C-SAR",
        relative_orbit=77,
        pass_direction=None,
        href="https://datapool.asf.alaska.edu/RTC/TEST_0001.tif",
    )


# --------------------------------------------------------------------------- #
# read_raster                                                                  #
# --------------------------------------------------------------------------- #


def test_reads_a_real_geotiff(tmp_path: Path) -> None:
    path = write_tif(tmp_path / "scene.tif", bimodal_scene())
    raster = read_raster(
        path,
        declared_band_order=(Polarization.VV, Polarization.VH),
        declared_scale=BackscatterScale.DECIBEL,
    )
    assert raster.spec.crs == "EPSG:32643"
    assert raster.spec.width == 64 and raster.spec.height == 64
    assert raster.spec.pixel_size_m == (10.0, 10.0)
    assert raster.data.shape == (2, 64, 64)


def test_band_descriptions_contradicting_the_declaration_are_refused(tmp_path: Path) -> None:
    """The check that would have caught the foundation commit's band-order error.

    The file says VV then VH. Declaring the reverse is refused rather than
    reconciled, because reading them mismatched normalises each channel with the
    other channel's statistics and nothing crashes.
    """
    path = write_tif(tmp_path / "scene.tif", bimodal_scene(), descriptions=("VV", "VH"))
    with pytest.raises(RasterReadError, match="described as VV but the caller declared VH"):
        read_raster(
            path,
            declared_band_order=(Polarization.VH, Polarization.VV),
            declared_scale=BackscatterScale.DECIBEL,
        )


def test_a_file_without_band_descriptions_falls_back_to_the_declaration(tmp_path: Path) -> None:
    """Plenty of valid products carry no band names; that is not an error."""
    path = write_tif(tmp_path / "scene.tif", bimodal_scene(), descriptions=None)
    raster = read_raster(
        path,
        declared_band_order=(Polarization.VH, Polarization.VV),
        declared_scale=BackscatterScale.DECIBEL,
    )
    assert raster.spec.band_order == (Polarization.VH, Polarization.VV)


def test_band_count_mismatch_is_refused(tmp_path: Path) -> None:
    path = write_tif(tmp_path / "scene.tif", bimodal_scene(), descriptions=("VV", "VH"))
    with pytest.raises(RasterReadError, match="2 band"):
        read_raster(
            path,
            declared_band_order=(Polarization.VV,),
            declared_scale=BackscatterScale.DECIBEL,
        )


def test_a_raster_without_a_crs_is_refused(tmp_path: Path) -> None:
    """Assuming EPSG:4326 here would be exactly the guess this package refuses."""
    path = tmp_path / "no_crs.tif"
    data = bimodal_scene()
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=64,
        width=64,
        count=2,
        dtype="float32",
        transform=from_origin(0, 0, 10, 10),
    ) as sink:
        sink.write(data.astype(np.float32))
    with pytest.raises(RasterReadError, match="no CRS"):
        read_raster(
            path,
            declared_band_order=(Polarization.VV, Polarization.VH),
            declared_scale=BackscatterScale.DECIBEL,
        )


def test_a_finite_nodata_sentinel_is_normalised_to_nan(tmp_path: Path) -> None:
    """So that ``isfinite`` is a complete validity test everywhere downstream.

    Review round one found ``validate_finite_fraction`` reporting a raster of
    -9999 as 100% valid, precisely because a finite sentinel travelled past the
    reader untouched.
    """
    data = bimodal_scene()
    data[:, :10, :] = -9999.0
    path = write_tif(tmp_path / "scene.tif", data, nodata=-9999.0)

    raster = read_raster(
        path,
        declared_band_order=(Polarization.VV, Polarization.VH),
        declared_scale=BackscatterScale.DECIBEL,
    )
    assert np.isnan(raster.band(Polarization.VV)[:10, :]).all()
    assert raster.spec.nodata is None  # the spec must not still advertise the sentinel


def test_band_lookup_is_by_name_not_index(tmp_path: Path) -> None:
    """Positional indexing is how the band-order defect propagates."""
    path = write_tif(tmp_path / "scene.tif", bimodal_scene())
    raster = read_raster(
        path,
        declared_band_order=(Polarization.VV, Polarization.VH),
        declared_scale=BackscatterScale.DECIBEL,
    )
    # VV is co-polarised and sits above VH; if the lookup were positional and the
    # order were swapped, this ordering would silently invert.
    assert raster.band(Polarization.VV).mean() > raster.band(Polarization.VH).mean()

    with pytest.raises(RasterReadError, match="no HH band"):
        raster.band(Polarization.HH)


def test_the_array_cannot_be_mutated_behind_a_validated_spec(tmp_path: Path) -> None:
    path = write_tif(tmp_path / "scene.tif", bimodal_scene())
    raster = read_raster(
        path,
        declared_band_order=(Polarization.VV, Polarization.VH),
        declared_scale=BackscatterScale.DECIBEL,
    )
    with pytest.raises(ValueError):
        raster.data[0, 0, 0] = 0.0


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RasterReadError, match="no such raster"):
        read_raster(
            tmp_path / "absent.tif",
            declared_band_order=(Polarization.VV,),
            declared_scale=BackscatterScale.DECIBEL,
        )


# --------------------------------------------------------------------------- #
# reprojection                                                                 #
# --------------------------------------------------------------------------- #


def test_a_geographic_raster_is_reprojected_to_its_own_utm_zone(tmp_path: Path) -> None:
    """The zone is chosen per-AOI, not hardcoded.

    An AOI on the Brahmaputra belongs in 46N. A single constant of 43N -- the
    approach in packages/geo/crs.py, raised as issue #15 -- is three zones off
    there, and produces a wrong hectare figure rather than an error.
    """
    path = write_tif(
        tmp_path / "geographic.tif",
        bimodal_scene(),
        crs="EPSG:4326",
        pixel_size=8.983152841195215e-05,
        origin=(92.5, 26.5),  # Brahmaputra valley, Assam
    )
    raster = read_raster(
        path,
        declared_band_order=(Polarization.VV, Polarization.VH),
        declared_scale=BackscatterScale.DECIBEL,
    )
    assert raster.spec.crs == "EPSG:4326"

    projected = reproject_to_area_safe_crs(raster)
    assert projected.spec.crs == "EPSG:32646"
    assert 8.0 < projected.spec.pixel_size_m[0] < 12.0  # ~10 m, now in metres


def test_a_raster_already_in_utm_is_returned_unchanged(tmp_path: Path) -> None:
    path = write_tif(tmp_path / "scene.tif", bimodal_scene(), crs="EPSG:32643")
    raster = read_raster(
        path,
        declared_band_order=(Polarization.VV, Polarization.VH),
        declared_scale=BackscatterScale.DECIBEL,
    )
    assert reproject_to_area_safe_crs(raster) is raster
