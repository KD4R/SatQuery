"""Calibration: temperature scaling, and the reliability diagram it is judged by.

Every test here uses synthetic data whose correct answer is known analytically,
because a calibration test on real model output can only assert that the number did
not change -- which passes just as happily when the number was wrong all along.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.evaluation.calibration import (
    apply_temperature,
    fit_temperature,
    negative_log_likelihood,
    reliability,
)

pytestmark = pytest.mark.unit


def perfectly_calibrated(size: int = 200_000, seed: int = 0):
    """Probabilities that mean exactly what they say, by construction."""
    rng = np.random.default_rng(seed)
    probabilities = rng.uniform(0.0, 1.0, size)
    labels = rng.uniform(0.0, 1.0, size) < probabilities
    return probabilities, labels


def test_a_perfectly_calibrated_model_has_near_zero_ece() -> None:
    probabilities, labels = perfectly_calibrated()
    result = reliability(probabilities, labels)
    assert result.ece < 0.01
    assert result.max_gap < 0.02


def test_an_overconfident_model_is_caught_and_the_sign_says_so() -> None:
    """Overconfidence is the failure mode a segmentation model actually has, and
    the one that matters: a caller thresholding at 0.9 for "high confidence"
    detections is relying on 0.9 meaning 0.9."""
    probabilities, labels = perfectly_calibrated()
    # Push every score toward its nearest extreme without changing any ordering.
    overconfident = np.clip(probabilities + 0.25 * np.sign(probabilities - 0.5), 0.0, 1.0)

    result = reliability(overconfident, labels)

    assert result.ece > 0.15
    populated = [b for b in result.bins if b.count > 0 and b.mean_confidence > 0.5]
    assert all(b.gap > 0 for b in populated), "confident bins must read as overconfident"


def test_ece_cannot_be_read_without_prevalence() -> None:
    """A model that outputs the base rate everywhere is perfectly calibrated and
    completely useless, which is why prevalence travels with the number."""
    rng = np.random.default_rng(1)
    labels = rng.uniform(0.0, 1.0, 100_000) < 0.1
    constant = np.full(labels.shape, 0.1)

    result = reliability(constant, labels)

    assert result.ece < 0.01
    assert result.prevalence == pytest.approx(0.1, abs=0.01)


def test_empty_bins_are_kept_rather_than_dropped() -> None:
    """An empty bin is information -- the model never expresses that confidence --
    and renumbering the rows would make two runs' diagrams incomparable."""
    probabilities = np.full(1000, 0.05)
    labels = np.zeros(1000, dtype=bool)

    result = reliability(probabilities, labels, bins=10)

    assert len(result.bins) == 10
    assert result.bins[0].count == 1000
    assert all(b.count == 0 for b in result.bins[1:])
    assert np.isnan(result.bins[5].mean_confidence)


def test_logits_passed_as_probabilities_are_refused() -> None:
    """The easiest way to produce a meaningless calibration report."""
    with pytest.raises(ValueError, match="look like logits"):
        reliability(np.array([-3.0, 2.0, 8.0]), np.array([0, 1, 1]))


def test_temperature_scaling_cannot_change_any_ranking() -> None:
    """The property that makes this safe to add to a branch carrying committed
    accuracy figures.

    Every IoU and F1 in reports/evaluation.md comes from thresholding. A monotonic
    one-parameter rescale cannot reorder two pixels, so no threshold-based number
    can move -- calibration is added without any reader having to wonder whether
    the model improved or the metric got friendlier.
    """
    rng = np.random.default_rng(2)
    logits = np.sort(rng.normal(0.0, 4.0, 10_000))

    for temperature in (0.1, 0.5, 1.0, 2.5, 17.0):
        scaled = apply_temperature(logits, temperature)
        # Non-decreasing, not strictly increasing. At small T the sigmoid
        # saturates and distinct logits map to the same float -- real, and the
        # reason fit_temperature's bounds are closed rather than open. It costs
        # nothing here: pixels that tie at 0.0 or 1.0 fall on the same side of
        # every threshold, so no mask changes.
        assert np.all(np.diff(scaled) >= 0)
        assert 0.0 <= scaled.min() and scaled.max() <= 1.0


def test_apply_temperature_survives_extreme_logits() -> None:
    """The naive sigmoid overflows below about -700 and returns nan, which then
    propagates into ECE as a silent nan rather than an error."""
    extreme = np.array([-5000.0, -700.0, 0.0, 700.0, 5000.0])
    result = apply_temperature(extreme, 1.0)
    assert np.all(np.isfinite(result))
    assert result[0] == pytest.approx(0.0)
    assert result[-1] == pytest.approx(1.0)
    assert result[2] == pytest.approx(0.5)


def test_fitting_recovers_a_known_temperature() -> None:
    """Generate labels from logits at T=1, present the model as if it were
    overconfident by a factor of three, and check the fit undoes exactly that."""
    rng = np.random.default_rng(3)
    honest_logits = rng.normal(0.0, 3.0, 400_000)
    labels = rng.uniform(0.0, 1.0, honest_logits.size) < apply_temperature(honest_logits, 1.0)

    overconfident = honest_logits * 3.0
    recovered = fit_temperature(overconfident, labels)

    assert recovered == pytest.approx(3.0, rel=0.05)


def test_fitting_an_already_calibrated_model_leaves_it_alone() -> None:
    rng = np.random.default_rng(4)
    logits = rng.normal(0.0, 3.0, 400_000)
    labels = rng.uniform(0.0, 1.0, logits.size) < apply_temperature(logits, 1.0)

    assert fit_temperature(logits, labels) == pytest.approx(1.0, rel=0.05)


def test_fitting_reduces_ece_on_an_overconfident_model() -> None:
    """The end-to-end claim, and the only one a reader of the report cares about."""
    rng = np.random.default_rng(5)
    honest = rng.normal(0.0, 3.0, 400_000)
    labels = rng.uniform(0.0, 1.0, honest.size) < apply_temperature(honest, 1.0)
    overconfident = honest * 3.0

    before = reliability(apply_temperature(overconfident, 1.0), labels).ece
    temperature = fit_temperature(overconfident, labels)
    after = reliability(apply_temperature(overconfident, temperature), labels).ece

    assert before > 0.1
    assert after < 0.02
    assert after < before / 5


def test_nll_is_minimised_at_the_fitted_temperature() -> None:
    rng = np.random.default_rng(6)
    logits = rng.normal(0.0, 3.0, 100_000) * 2.0
    labels = rng.uniform(0.0, 1.0, logits.size) < apply_temperature(logits / 2.0, 1.0)

    best = fit_temperature(logits, labels)
    at_best = negative_log_likelihood(logits, labels, best)

    for other in (best * 0.5, best * 0.8, best * 1.25, best * 2.0):
        assert negative_log_likelihood(logits, labels, other) >= at_best


@pytest.mark.parametrize("temperature", [0.0, -1.0, float("nan"), float("inf")])
def test_a_nonsensical_temperature_is_refused(temperature: float) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        apply_temperature(np.array([0.0]), temperature)


def test_mismatched_lengths_are_refused() -> None:
    with pytest.raises(ValueError, match="same flat length"):
        reliability(np.array([0.1, 0.2]), np.array([1]))
    with pytest.raises(ValueError, match="logits against"):
        fit_temperature(np.array([0.1, 0.2]), np.array([1]))


def test_measuring_nothing_is_an_error() -> None:
    with pytest.raises(ValueError, match="zero samples"):
        reliability(np.array([]), np.array([]))
    with pytest.raises(ValueError, match="zero samples"):
        fit_temperature(np.array([]), np.array([]))
