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
from ml.io.raster import Raster, RasterReadError, read_raster, reproject_to_area_safe_crs
from ml.pipeline.baseline import (
    detect_water_single_date,
    water_mask_single_date,
)
from ml.preflight.raster import PreflightError
from ml.sar.change import ThresholdError

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


# --------------------------------------------------------------------------- #
# the baseline                                                                 #
# --------------------------------------------------------------------------- #


def _read(tmp_path: Path, data: np.ndarray, **kwargs) -> Raster:
    path = write_tif(tmp_path / "scene.tif", data, **kwargs)
    return read_raster(
        path,
        declared_band_order=(Polarization.VV, Polarization.VH),
        declared_scale=BackscatterScale.DECIBEL,
    )


def test_water_is_selected_below_the_threshold_not_above(tmp_path: Path) -> None:
    """Water is dark in SAR. Inverting this yields a mask of everything that is
    NOT flooded -- plausible, and entirely wrong, so it is pinned by test."""
    raster = _read(tmp_path, bimodal_scene(water_rows=20))
    detection = water_mask_single_date(raster)

    assert detection.mask[:20, :].mean() > 0.95  # the dark region is water
    assert detection.mask[25:, :].mean() < 0.05  # the bright region is not
    assert -20.0 < detection.threshold_db < -8.0


def test_the_measured_area_matches_the_synthetic_extent(tmp_path: Path) -> None:
    """20 rows of 64 px at 10 m is 20*64*100 m^2 = 12.8 ha."""
    raster = _read(tmp_path, bimodal_scene(water_rows=20))
    outcome = detect_water_single_date(
        raster, scenes=[a_scene_ref()], code_version="0.1.0", trace_id="t-area"
    )
    assert outcome.outcome == "analysed"
    assert float(outcome.measurements[0].value) == pytest.approx(12.8, abs=0.3)
    assert outcome.measurements[0].crs == "EPSG:32643"


def test_the_analysis_carries_provenance_and_an_uncalibrated_confidence(
    tmp_path: Path,
) -> None:
    """A baseline number must not present itself as a calibrated one."""
    raster = _read(tmp_path, bimodal_scene())
    outcome = detect_water_single_date(
        raster, scenes=[a_scene_ref()], code_version="0.1.0", trace_id="t-prov"
    )
    assert outcome.outcome == "analysed"

    measurement = outcome.measurements[0]
    assert measurement.produced_by == "ml.geo.area.area_hectares"
    assert measurement.derived_from == (a_scene_ref(),)
    assert outcome.confidence is not None
    assert outcome.confidence.value is None
    assert outcome.confidence.basis.value == "not_calibrated"
    assert any("deterministic baseline" in c for c in outcome.caveats)


def test_a_geographic_raster_abstains_rather_than_measuring_degrees(tmp_path: Path) -> None:
    """The pipeline refuses to measure before reprojection, rather than doing it
    implicitly -- the raster needs bilinear resampling and a mask needs nearest,
    so the ordering must stay explicit."""
    raster = _read(
        tmp_path,
        bimodal_scene(),
        crs="EPSG:4326",
        pixel_size=8.983152841195215e-05,
        origin=(76.4, 9.5),
    )
    outcome = detect_water_single_date(
        raster, scenes=[a_scene_ref()], code_version="0.1.0", trace_id="t-geo"
    )
    assert outcome.outcome == "abstained"
    assert outcome.reason.value == "input_failed_preflight"
    assert "EPSG:4326" in outcome.explanation


def test_a_mostly_nodata_chip_abstains(tmp_path: Path) -> None:
    """An area from a sliver of the AOI describes it as though it were the whole."""
    data = bimodal_scene()
    data[:, :56, :] = np.nan  # 87.5% no-data
    raster = _read(tmp_path, data)

    outcome = detect_water_single_date(
        raster, scenes=[a_scene_ref()], code_version="0.1.0", trace_id="t-nodata"
    )
    assert outcome.outcome == "abstained"
    assert outcome.reason.value == "input_failed_preflight"


def test_a_constant_scene_abstains_rather_than_inventing_a_threshold(tmp_path: Path) -> None:
    raster = _read(tmp_path, np.full((2, 64, 64), -10.0))
    outcome = detect_water_single_date(
        raster, scenes=[a_scene_ref()], code_version="0.1.0", trace_id="t-flat"
    )
    assert outcome.outcome == "abstained"
    assert outcome.reason.value == "no_separable_threshold"


def test_permanent_water_is_subtracted(tmp_path: Path) -> None:
    """A permanent lake reported as flooding is the most embarrassing failure this
    pipeline can have, and it happens on every scene containing one."""
    raster = _read(tmp_path, bimodal_scene(water_rows=20))

    permanent = np.zeros((64, 64), dtype=bool)
    permanent[:10, :] = True  # half the dark region is a lake, not a flood

    with_lake = detect_water_single_date(
        raster,
        scenes=[a_scene_ref()],
        code_version="0.1.0",
        trace_id="t-perm",
        permanent_water=permanent,
    )
    without = detect_water_single_date(
        raster, scenes=[a_scene_ref()], code_version="0.1.0", trace_id="t-noperm"
    )
    assert with_lake.outcome == "analysed" and without.outcome == "analysed"
    assert float(with_lake.measurements[0].value) < float(without.measurements[0].value)
    assert any("permanent water subtracted" in c for c in with_lake.caveats)


def test_a_misregistered_permanent_water_mask_abstains(tmp_path: Path) -> None:
    raster = _read(tmp_path, bimodal_scene())
    outcome = detect_water_single_date(
        raster,
        scenes=[a_scene_ref()],
        code_version="0.1.0",
        trace_id="t-shape",
        permanent_water=np.zeros((32, 32), dtype=bool),
    )
    assert outcome.outcome == "abstained"
    assert "co-registered" in outcome.explanation


def test_the_mask_the_pipeline_reports_is_the_mask_evaluation_scores(
    tmp_path: Path,
) -> None:
    """One implementation of the rule, not two.

    ``water_mask_single_date`` was split out of the pipeline entry point precisely
    so the evaluation harness cannot drift from what the pipeline does. This pins
    that they agree.
    """
    raster = _read(tmp_path, bimodal_scene(water_rows=20))
    detection = water_mask_single_date(raster)
    outcome = detect_water_single_date(
        raster, scenes=[a_scene_ref()], code_version="0.1.0", trace_id="t-same"
    )
    assert outcome.outcome == "analysed"

    pixel_area = 10.0 * 10.0
    expected_hectares = int(np.count_nonzero(detection.mask)) * pixel_area / 10_000.0
    assert float(outcome.measurements[0].value) == pytest.approx(expected_hectares, abs=0.05)


def test_raising_and_abstaining_paths_agree_on_when_to_fail(tmp_path: Path) -> None:
    """Whatever makes the low-level function raise must make the pipeline abstain."""
    raster = _read(tmp_path, np.full((2, 64, 64), -10.0))
    with pytest.raises((ThresholdError, PreflightError)):
        water_mask_single_date(raster)

    outcome = detect_water_single_date(
        raster, scenes=[a_scene_ref()], code_version="0.1.0", trace_id="t-agree"
    )
    assert outcome.outcome == "abstained"
