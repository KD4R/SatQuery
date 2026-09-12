"""Backscatter scale conversion, with the double-conversion trap closed.

The trap
--------
``to_db`` applied twice produces a plausible array of plausible numbers that is
wrong. So does ``to_db`` applied to data that was already in decibels -- which is
exactly what happens if someone runs the standard preprocessing over a
Sen1Floods11 chip, because those chips are *already* stored in dB.

The fix is not discipline, it is refusing to accept an array without being told
what scale it is in. :func:`ensure_decibel` takes the declared scale as a required
argument and converts only when conversion is actually needed. There is no code
path here that infers the scale from the values, because the two distributions
overlap enough that inference would sometimes be wrong -- and a sometimes-wrong
silent conversion is worse than no conversion at all.

Reference for the scale options available at ordering time:
    ASF HyP3 Sentinel-1 RTC Product Guide,
    https://hyp3-docs.asf.alaska.edu/guides/rtc_product_guide/
    "power (default), amplitude, decibel"
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from ml.contracts.scene import BackscatterScale

#: Power values at or below this are treated as invalid rather than converted.
#: log10 of zero is -inf and of a negative number is undefined; RTC products
#: legitimately contain zeros in radar shadow, so those become NaN (no data)
#: rather than -inf, which would poison any subsequent statistic.
_MIN_VALID_POWER = 0.0


class ScaleError(ValueError):
    """Raised when a conversion between backscatter scales cannot be performed."""


def power_to_db(power: npt.NDArray[np.floating]) -> npt.NDArray[np.floating]:
    """Convert linear power (gamma-nought or sigma-nought) to decibels.

    ``dB = 10 * log10(power)``

    Non-positive samples -- radar shadow, masked pixels, genuine zeros -- become
    ``NaN`` rather than ``-inf``. ``-inf`` propagates through means and histograms
    in ways that are hard to notice; ``NaN`` is excluded explicitly by every
    downstream statistic in this package.
    """
    result = np.full(power.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(power) & (power > _MIN_VALID_POWER)
    # np.log10 is only evaluated on the valid subset, so no warning is emitted for
    # the masked entries.
    result[valid] = 10.0 * np.log10(power[valid].astype(np.float64))
    return result


def db_to_power(db: npt.NDArray[np.floating]) -> npt.NDArray[np.floating]:
    """Convert decibels back to linear power. Inverse of :func:`power_to_db`."""
    result = np.full(db.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(db)
    result[valid] = np.power(10.0, db[valid].astype(np.float64) / 10.0)
    return result


def amplitude_to_db(amplitude: npt.NDArray[np.floating]) -> npt.NDArray[np.floating]:
    """Convert amplitude to decibels.

    Amplitude is the square root of power, so ``dB = 20 * log10(amplitude)``.
    Implemented by squaring and delegating, which keeps the invalid-sample handling
    in exactly one place.

    Negative samples are mapped to ``NaN`` *before* squaring. Squaring first would
    launder them: amplitude is by definition a non-negative magnitude, so a value
    of ``-1`` is a corrupt or mis-scaled sample, yet ``(-1) ** 2`` is ``1`` and
    converts cleanly to ``0 dB``. An invalid pixel silently becoming a plausible
    backscatter reading is exactly the failure this module exists to prevent, and
    it matches how ``power_to_db`` already treats non-positive power.
    """
    a = amplitude.astype(np.float64)
    with np.errstate(invalid="ignore"):
        valid = np.where(a >= 0.0, a, np.nan)
    return power_to_db(np.square(valid))


def ensure_decibel(
    array: npt.NDArray[np.floating],
    declared_scale: BackscatterScale,
) -> npt.NDArray[np.floating]:
    """Return ``array`` in decibels, converting only if the declared scale requires it.

    This is the only function the pipeline should use to normalise scale. It takes
    the *declared* scale rather than guessing, so calling it twice on the same data
    is safe as long as the caller updates the declaration -- and calling it on data
    already in dB is a no-op rather than a corruption.

    Parameters
    ----------
    array
        Raster values.
    declared_scale
        What :class:`~ml.contracts.scene.RasterSpec` says these values are
        in. This comes from provider metadata or from the dataset documentation --
        never from inspecting the values.

    Raises
    ------
    ScaleError
        If the declared scale is not one this function knows how to convert.
    """
    if declared_scale is BackscatterScale.DECIBEL:
        # Already in the target scale. Returned as-is rather than round-tripped,
        # because a needless power->dB->power round trip loses precision.
        return array
    if declared_scale is BackscatterScale.POWER:
        return power_to_db(array)
    if declared_scale is BackscatterScale.AMPLITUDE:
        return amplitude_to_db(array)
    raise ScaleError(f"cannot convert from unknown scale {declared_scale!r} to decibels")
