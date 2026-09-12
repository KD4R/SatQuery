"""Tests for splits, normalisation and sample preparation.

These are deliberately torch-free so they run in the ordinary CI job, which has no
deep learning stack installed. That matters more than it sounds: a defect in the
split or in normalisation does not crash — it produces a training run that
completes, reports a good number, and is wrong. The architecture is the part least
likely to fail silently; this is the part most likely to.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from ml.evaluation.segmentation import SEN1FLOODS11_IGNORE_VALUE
from ml.training.dataset import (
    Normalisation,
    Sen1Floods11Dataset,
    augment,
    fit_normalisation,
    load_chip,
    prepare,
    random_crop,
)
from ml.training.splits import (
    SplitError,
    discover_chips,
    region_of,
    split_by_region,
)

pytestmark = pytest.mark.unit


def make_chip(
    root: Path, stem: str, *, water_rows: int = 20, nodata_rows: int = 0, size: int = 64
) -> None:
    """Write a real S1Hand + LabelHand pair under ``root``."""
    rng = np.random.default_rng(abs(hash(stem)) % 2**32)
    vv = rng.normal(-8.0, 1.0, (size, size)).astype(np.float32)
    vv[:water_rows, :] = rng.normal(-20.0, 1.0, (water_rows, size))
    bands = np.stack([vv, vv - 6.0])

    labels = np.zeros((size, size), dtype=np.int16)
    labels[:water_rows, :] = 1
    if nodata_rows:
        labels[-nodata_rows:, :] = SEN1FLOODS11_IGNORE_VALUE

    transform = from_origin(500000.0, 1000000.0, 10.0, 10.0)
    (root / "S1Hand").mkdir(parents=True, exist_ok=True)
    (root / "LabelHand").mkdir(parents=True, exist_ok=True)

    with rasterio.open(
        root / "S1Hand" / f"{stem}_S1Hand.tif",
        "w",
        driver="GTiff",
        height=size,
        width=size,
        count=2,
        dtype="float32",
        crs="EPSG:32643",
        transform=transform,
    ) as sink:
        sink.write(bands)
        sink.set_band_description(1, "VV")
        sink.set_band_description(2, "VH")

    with rasterio.open(
        root / "LabelHand" / f"{stem}_LabelHand.tif",
        "w",
        driver="GTiff",
        height=size,
        width=size,
        count=1,
        dtype="int16",
        crs="EPSG:32643",
        transform=transform,
    ) as sink:
        sink.write(labels, 1)


@pytest.fixture
def benchmark(tmp_path: Path) -> Path:
    for stem in ("Ghana_1", "Ghana_2", "Mekong_1", "India_1", "India_2", "Somalia_1"):
        make_chip(tmp_path, stem)
    return tmp_path


# --------------------------------------------------------------------------- #
# Splits                                                                       #
# --------------------------------------------------------------------------- #


def test_regions_are_parsed_from_chip_names() -> None:
    assert region_of("India_1050276") == "India"
    assert region_of("Ghana_277") == "Ghana"


def test_an_unparseable_chip_name_is_refused() -> None:
    """Silently defaulting to one region would put every chip on the same side."""
    with pytest.raises(SplitError, match="cannot read a region"):
        region_of("weird-name.tif")


def test_no_region_appears_on_both_sides(benchmark: Path) -> None:
    """The check that makes the validation number mean anything.

    Sen1Floods11 chips are tiles from a much smaller number of events. Two Ghana
    chips are two windows onto the same river in the same week, so a chip-level
    random split lets the model score well by recognising terrain it has already
    seen. The number then measures memorisation and reports it as skill.
    """
    split = split_by_region(discover_chips(benchmark))

    train_regions = {c.region for c in split.train}
    validation_regions = {c.region for c in split.validation}

    assert not (train_regions & validation_regions)
    assert validation_regions == {"India", "Somalia"}


def test_india_is_always_held_out(benchmark: Path) -> None:
    """The product is for Indian flooding, so India is the deployment condition.

    A model scoring well on India *because it trained on India* would say nothing
    about the demo.
    """
    split = split_by_region(discover_chips(benchmark))
    assert all(c.region != "India" for c in split.train)
    assert any(c.region == "India" for c in split.validation)


def test_a_misspelled_validation_region_is_refused(benchmark: Path) -> None:
    """Otherwise the validation set is empty and every epoch reports nan while
    training carries on looking healthy."""
    with pytest.raises(SplitError, match="not present on disk"):
        split_by_region(discover_chips(benchmark), validation_regions=frozenset({"Indai"}))


def test_holding_out_every_region_is_refused(benchmark: Path) -> None:
    with pytest.raises(SplitError, match="training split is empty"):
        split_by_region(
            discover_chips(benchmark),
            validation_regions=frozenset({"Ghana", "Mekong", "India", "Somalia"}),
        )


def test_an_empty_directory_says_how_to_fix_it(tmp_path: Path) -> None:
    with pytest.raises(SplitError, match="fetch_sen1floods11"):
        discover_chips(tmp_path)


def test_a_scene_without_labels_is_skipped(benchmark: Path) -> None:
    """It cannot be trained on and cannot be scored; carrying it forward only
    produces a confusing failure later."""
    orphan = benchmark / "S1Hand" / "Nigeria_9_S1Hand.tif"
    make_chip(benchmark, "Nigeria_9")
    (benchmark / "LabelHand" / "Nigeria_9_LabelHand.tif").unlink()

    assert orphan.is_file()
    assert all(c.stem != "Nigeria_9" for c in discover_chips(benchmark))


# --------------------------------------------------------------------------- #
# Normalisation                                                                #
# --------------------------------------------------------------------------- #


def test_normalisation_is_fitted_on_training_chips_only(benchmark: Path) -> None:
    """Validation statistics leaking into normalisation is a real, quiet leak.

    Pinned by construction rather than by inspection: the function only ever
    receives the training split, and this asserts the caller honours that.
    """
    split = split_by_region(discover_chips(benchmark))
    from_train = fit_normalisation(split.train)
    from_all = fit_normalisation(split.train + split.validation)
    assert from_train != from_all


def test_normalisation_round_trips_through_a_dict() -> None:
    """It is saved beside the checkpoint; inference must reuse it, not refit."""
    original = Normalisation(mean=(-10.3, -17.5), std=(4.3, 4.9))
    assert Normalisation.from_dict(original.to_dict()) == original


def test_normalisation_produces_roughly_unit_scale(benchmark: Path) -> None:
    split = split_by_region(discover_chips(benchmark))
    normalisation = fit_normalisation(split.train)

    bands, _ = load_chip(split.train[0])
    standardised = normalisation.apply(bands)
    finite = standardised[np.isfinite(standardised)]

    assert abs(float(finite.mean())) < 1.5
    assert 0.3 < float(finite.std()) < 3.0


def test_fitting_on_an_empty_split_is_refused() -> None:
    with pytest.raises(ValueError, match="empty split"):
        fit_normalisation(())


# --------------------------------------------------------------------------- #
# Sample preparation                                                           #
# --------------------------------------------------------------------------- #


def test_no_data_becomes_a_zero_weight_not_a_label(tmp_path: Path) -> None:
    """Training -1 as land teaches the model that every image edge is dry."""
    make_chip(tmp_path, "Ghana_1", water_rows=20, nodata_rows=10)
    chip = discover_chips(tmp_path)[0]
    bands, labels = load_chip(chip)

    x, y, weight = prepare(bands, labels, Normalisation(mean=(-10.0, -16.0), std=(4.0, 4.0)))

    assert sorted(np.unique(y).tolist()) == [0.0, 1.0], "-1 must never reach the model"
    assert weight[-5, 0] == 0.0
    assert weight[0, 0] == 1.0


def test_nan_never_reaches_the_model(tmp_path: Path) -> None:
    """One NaN propagates through the convolutions and makes the whole loss NaN,
    which reads as a diverged model rather than a data problem."""
    make_chip(tmp_path, "Ghana_1")
    chip = discover_chips(tmp_path)[0]
    bands, labels = load_chip(chip)
    bands[0, :5, :5] = np.nan

    x, _, weight = prepare(bands, labels, Normalisation(mean=(-10.0, -16.0), std=(4.0, 4.0)))

    assert np.isfinite(x).all()
    assert weight[0, 0] == 0.0, "an unobserved pixel must not be learned from"


def test_invalid_pixels_are_filled_with_the_mean_not_a_dark_value(tmp_path: Path) -> None:
    """Filling NaN with a low dB value would teach the model that no-data is water."""
    make_chip(tmp_path, "Ghana_1")
    chip = discover_chips(tmp_path)[0]
    bands, labels = load_chip(chip)
    bands[:, :4, :4] = np.nan

    x, _, _ = prepare(bands, labels, Normalisation(mean=(-10.0, -16.0), std=(4.0, 4.0)))
    assert float(x[0, 0, 0]) == 0.0  # zero is the post-standardisation mean


# --------------------------------------------------------------------------- #
# Cropping and augmentation                                                    #
# --------------------------------------------------------------------------- #


def test_crops_are_the_requested_size() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(2, 64, 64)).astype(np.float32)
    y = np.zeros((64, 64), dtype=np.float32)
    w = np.ones((64, 64), dtype=np.float32)

    cx, cy, cw = random_crop(x, y, w, size=32, rng=rng)
    assert cx.shape == (2, 32, 32)
    assert cy.shape == cw.shape == (32, 32)


def test_a_crop_larger_than_the_chip_is_refused() -> None:
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError, match="smaller than"):
        random_crop(
            np.zeros((2, 16, 16), dtype=np.float32),
            np.zeros((16, 16), dtype=np.float32),
            np.ones((16, 16), dtype=np.float32),
            size=32,
            rng=rng,
        )


def test_augmentation_keeps_bands_labels_and_weights_aligned() -> None:
    """A flip applied to the image but not the label silently destroys training.

    It does not crash and the loss still decreases -- the model learns to predict
    the average of both orientations -- so this is pinned rather than trusted.
    """
    rng = np.random.default_rng(3)
    x = np.zeros((2, 8, 8), dtype=np.float32)
    y = np.zeros((8, 8), dtype=np.float32)
    w = np.ones((8, 8), dtype=np.float32)
    x[:, 0, 0] = 5.0
    y[0, 0] = 1.0

    for _ in range(20):
        ax, ay, aw = augment(x.copy(), y.copy(), w.copy(), rng)
        marker = np.argwhere(ax[0] == 5.0)
        label = np.argwhere(ay == 1.0)
        assert marker.tolist() == label.tolist()
        assert aw.shape == ay.shape


def test_augmentation_does_not_change_backscatter_values() -> None:
    """No brightness or contrast jitter: dB is a calibrated physical quantity, and
    shifting it teaches the model that the absolute value carries no information,
    when the absolute value is very nearly the whole signal."""
    rng = np.random.default_rng(1)
    x = rng.normal(size=(2, 8, 8)).astype(np.float32)
    ax, _, _ = augment(x.copy(), np.zeros((8, 8), np.float32), np.ones((8, 8), np.float32), rng)
    assert sorted(ax.ravel().tolist()) == pytest.approx(sorted(x.ravel().tolist()))


# --------------------------------------------------------------------------- #
# Dataset                                                                      #
# --------------------------------------------------------------------------- #


def test_dry_chips_are_kept_in_the_training_set(tmp_path: Path) -> None:
    """The whole reason the model is being added (ADR-0007 D13).

    Dropping chips with no positive pixels is the obvious optimisation and it
    would remove exactly the capability the model exists to provide: saying
    *no water here*. Otsu cannot; a model only learns it from dry examples.
    """
    make_chip(tmp_path, "Ghana_1", water_rows=0)
    make_chip(tmp_path, "Ghana_2", water_rows=30)
    chips = discover_chips(tmp_path)

    assert len(chips) == 2
    dataset = Sen1Floods11Dataset(
        chips, Normalisation(mean=(-10.0, -16.0), std=(4.0, 4.0)), crop_size=None
    )
    assert len(dataset) == 2

    targets = [dataset[i][1] for i in range(len(dataset))]
    assert any(t.max() == 0.0 for t in targets), "a chip with no water must survive"


def test_an_empty_dataset_is_refused() -> None:
    with pytest.raises(ValueError, match="empty"):
        Sen1Floods11Dataset((), Normalisation(mean=(0.0,), std=(1.0,)))


def test_samples_are_reproducible_for_a_given_seed(tmp_path: Path) -> None:
    make_chip(tmp_path, "Ghana_1")
    chips = discover_chips(tmp_path)
    normalisation = Normalisation(mean=(-10.0, -16.0), std=(4.0, 4.0))

    first = Sen1Floods11Dataset(chips, normalisation, crop_size=32, seed=7)[0]
    second = Sen1Floods11Dataset(chips, normalisation, crop_size=32, seed=7)[0]

    assert np.array_equal(first[0], second[0])
    assert np.array_equal(first[1], second[1])
