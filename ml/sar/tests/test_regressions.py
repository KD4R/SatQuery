"""Regression tests for defects found in review of the foundation commit.

Their shared property is what makes them worth keeping: **each one passed
silently before the fix.** Not one produced an exception, a warning or a visibly
odd value -- they produced plausible wrong numbers, which is the failure mode this
subsystem exists to prevent, and they got past a reviewer who had just written the
trap list.

Distributed from a single module into each package's own tests at review
(PR #17), to follow the repository's co-location convention.

Reference: https://github.com/KD4R/SatQuery/pull/17
"""

from __future__ import annotations


import numpy as np
import pytest

from ml.sar.units import amplitude_to_db

pytestmark = pytest.mark.unit


def test_negative_amplitude_becomes_nan_not_zero_db() -> None:
    """Squaring laundered invalid samples into plausible backscatter.

    Amplitude is by definition non-negative, so ``-1`` is corrupt or mis-scaled.
    Squaring first turns it into ``1``, which converts to a clean ``0 dB`` -- a
    value in the middle of the plausible range for a bright urban scatterer. The
    invalid pixel then contributes to the Otsu histogram as though it were an
    observation.
    """
    out = amplitude_to_db(np.array([-1.0, -0.5, 0.0, 2.0]))
    assert np.isnan(out[0])
    assert np.isnan(out[1])
    assert np.isnan(out[2])  # zero amplitude is also unmeasurable, matching power_to_db
    assert np.isclose(out[3], 20.0 * np.log10(2.0))


def test_valid_amplitude_is_unchanged_by_the_guard() -> None:
    amplitudes = np.array([0.5, 1.0, 3.0, 10.0])
    assert np.allclose(amplitude_to_db(amplitudes), 20.0 * np.log10(amplitudes))
