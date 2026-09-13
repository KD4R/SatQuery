"""SAR scale conversion, log-ratio and Otsu thresholding.

These tests pin the two defects that produce plausible wrong answers rather than
exceptions: double dB conversion, and an inverted flood-signal direction.
"""

from __future__ import annotations

import numpy as np
import pytest

from packages.contracts import BackscatterScale
from ml.sar.change import (
    ThresholdError,
    log_ratio_db,
    otsu_threshold,
    water_mask_from_change,
)
from ml.sar.units import (
    ScaleError,
    amplitude_to_db,
    db_to_power,
    ensure_decibel,
    power_to_db,
)

# CI selects tests by marker (`pytest -m unit`); an unmarked test never runs.
# Everything in this module is a fast, offline, no-I/O unit test.
pytestmark = pytest.mark.unit

# --------------------------------------------------------------------------- #
# Scale conversion                                                             #
# --------------------------------------------------------------------------- #


def test_power_to_db_known_values() -> None:
    """10*log10 of 1 is 0 dB; of 0.1 is -10 dB; of 0.01 is -20 dB."""
    power = np.array([1.0, 0.1, 0.01], dtype=np.float32)
    db = power_to_db(power)
    np.testing.assert_allclose(db, [0.0, -10.0, -20.0], atol=1e-4)


def test_power_to_db_maps_nonpositive_to_nan_not_negative_infinity() -> None:
    """Radar shadow is a legitimate zero. -inf would poison every later statistic."""
    power = np.array([0.0, -1.0, 0.5], dtype=np.float32)
    db = power_to_db(power)
    assert np.isnan(db[0])
    assert np.isnan(db[1])
    assert np.isfinite(db[2])


def test_db_to_power_round_trips() -> None:
    power = np.array([1.0, 0.1, 0.5], dtype=np.float32)
    np.testing.assert_allclose(db_to_power(power_to_db(power)), power, rtol=1e-5)


def test_amplitude_to_db_is_twenty_log10() -> None:
    """Amplitude is sqrt(power), so dB = 20*log10(amplitude)."""
    amplitude = np.array([1.0, 0.1], dtype=np.float32)
    np.testing.assert_allclose(amplitude_to_db(amplitude), [0.0, -20.0], atol=1e-4)


def test_ensure_decibel_is_a_noop_on_data_already_in_db() -> None:
    """THE trap. Sen1Floods11 chips are already dB; converting again corrupts them.

    ``ensure_decibel`` takes the declared scale, so it knows not to convert. If
    this ever regresses, every number the subsystem produces from training data is
    wrong and nothing raises.
    """
    already_db = np.array([-9.26, -15.80, -3.0], dtype=np.float32)
    out = ensure_decibel(already_db, BackscatterScale.DECIBEL)
    np.testing.assert_array_equal(out, already_db)


def test_ensure_decibel_converts_power() -> None:
    power = np.array([1.0, 0.1], dtype=np.float32)
    np.testing.assert_allclose(
        ensure_decibel(power, BackscatterScale.POWER), [0.0, -10.0], atol=1e-4
    )


def test_ensure_decibel_converts_amplitude() -> None:
    amplitude = np.array([1.0, 0.1], dtype=np.float32)
    np.testing.assert_allclose(
        ensure_decibel(amplitude, BackscatterScale.AMPLITUDE), [0.0, -20.0], atol=1e-4
    )


def test_ensure_decibel_rejects_unknown_scale() -> None:
    with pytest.raises(ScaleError):
        ensure_decibel(np.array([1.0]), "not-a-scale")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Log-ratio                                                                    #
# --------------------------------------------------------------------------- #


def test_log_ratio_in_db_domain_is_a_difference() -> None:
    """log10(post/pre) in dB is post_dB - pre_dB. The log is already in the units."""
    pre = np.array([[-10.0, -5.0]], dtype=np.float32)
    post = np.array([[-18.0, -5.0]], dtype=np.float32)
    np.testing.assert_allclose(log_ratio_db(pre, post), [[-8.0, 0.0]], atol=1e-5)


def test_log_ratio_propagates_nan() -> None:
    """A pixel invalid in either epoch has no valid change value -- not zero change."""
    pre = np.array([np.nan, -5.0], dtype=np.float32)
    post = np.array([-10.0, -5.0], dtype=np.float32)
    result = log_ratio_db(pre, post)
    assert np.isnan(result[0])
    assert result[1] == pytest.approx(0.0)


def test_log_ratio_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="identical shape"):
        log_ratio_db(np.zeros((4, 4), dtype=np.float32), np.zeros((4, 5), dtype=np.float32))


# --------------------------------------------------------------------------- #
# Otsu                                                                         #
# --------------------------------------------------------------------------- #


def test_otsu_separates_a_known_bimodal_distribution(bimodal_change: np.ndarray) -> None:
    """Modes at -8 dB and +1 dB: the threshold must actually separate them.

    Note what is asserted and what is not. The exact threshold value is *not*
    pinned, because between-class variance is almost flat across an empty gap
    between two well-separated clusters -- every candidate in the gap yields
    nearly the same score, so ``argmax`` lands somewhere in it for reasons that
    amount to floating-point noise. Asserting a narrow numeric window would
    therefore be testing the noise, and would break on any harmless refactor.

    What matters is the property: does the chosen threshold classify the two
    populations correctly? That is stable, meaningful, and is what the pipeline
    actually depends on.
    """
    threshold = otsu_threshold(bimodal_change)

    # The fixture is [flooded (2048 samples near -8 dB), unchanged (2048 near +1)].
    flooded, unchanged = bimodal_change[:2048], bimodal_change[2048:]

    assert -8.0 < threshold < 1.0, "threshold must fall between the two modes"

    correctly_flooded = float(np.mean(flooded < threshold))
    correctly_unchanged = float(np.mean(unchanged >= threshold))
    assert correctly_flooded > 0.98
    assert correctly_unchanged > 0.98


def test_otsu_ignores_nan(bimodal_change: np.ndarray) -> None:
    """No-data must not drag the threshold; it is excluded, not treated as a value."""
    clean = otsu_threshold(bimodal_change)
    with_nan = np.concatenate([bimodal_change, np.full(500, np.nan, dtype=np.float32)])
    assert otsu_threshold(with_nan) == pytest.approx(clean, abs=0.3)


def test_otsu_refuses_a_unimodal_distribution() -> None:
    """All-water or all-land: no threshold separates two classes, so abstain."""
    constant = np.full(1000, -7.0, dtype=np.float32)
    with pytest.raises(ThresholdError, match=r"unimodal|degenerate"):
        otsu_threshold(constant)


def test_otsu_refuses_when_almost_everything_is_nodata() -> None:
    """A confident mask computed from 0.2% of the pixels is worse than no mask."""
    mostly_nan = np.full(1000, np.nan, dtype=np.float32)
    mostly_nan[:2] = [-8.0, 1.0]
    with pytest.raises(ThresholdError, match="refusing to threshold"):
        otsu_threshold(mostly_nan)


def test_otsu_refuses_all_nan() -> None:
    with pytest.raises(ThresholdError, match="no finite values"):
        otsu_threshold(np.full(100, np.nan, dtype=np.float32))


# --------------------------------------------------------------------------- #
# Flood signal direction -- the sign trap                                      #
# --------------------------------------------------------------------------- #


def test_water_is_selected_where_backscatter_decreased() -> None:
    """Water is specular, so it is DARK in SAR: flooding lowers backscatter.

    Getting this backwards yields a mask of everything that is *not* flooded --
    plausible-looking, entirely wrong. Hence an explicit test rather than a comment.
    """
    change = np.array([[-8.0, 0.5], [-9.0, 2.0]], dtype=np.float32)
    mask = water_mask_from_change(change, threshold_db=-4.0)

    assert mask[0, 0] is np.True_ or bool(mask[0, 0]) is True  # -8.0 < -4.0 -> water
    assert bool(mask[1, 0]) is True  # -9.0 < -4.0 -> water
    assert bool(mask[0, 1]) is False  # +0.5 -> not water
    assert bool(mask[1, 1]) is False  # +2.0 -> not water


def test_nodata_is_never_counted_as_water() -> None:
    """Counting no-data as water inflates extent -- a failure biased toward alarm."""
    change = np.array([np.nan, -8.0, np.nan], dtype=np.float32)
    mask = water_mask_from_change(change, threshold_db=-4.0)
    assert bool(mask[0]) is False
    assert bool(mask[1]) is True
    assert bool(mask[2]) is False
