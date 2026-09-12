"""Bi-temporal change detection primitives: log-ratio and Otsu thresholding.

Why log-ratio rather than a plain difference
--------------------------------------------
SAR speckle is *multiplicative*, not additive. A linear difference between two
power images therefore has a noise term proportional to the local backscatter,
which means bright targets dominate the change map regardless of whether anything
happened there. Taking the ratio converts the multiplicative noise into an additive
one, which is well behaved and roughly stationary across the scene.

In the decibel domain the log has already been taken, so the ratio becomes a
subtraction:

    log_ratio_dB = post_dB - pre_dB      (equivalently 10 * log10(post_power / pre_power))

This is why :func:`log_ratio_db` looks like a plain difference. It is a ratio; the
logarithm is already in the units. Applying a *linear* difference to dB data would
be a different and incorrect operation, which is the reason this module refuses to
accept anything but decibels.

Flood signal direction
----------------------
Open water is specular at radar wavelengths: it reflects energy away from the
sensor rather than back to it, so flooded ground appears **dark**. Flooding
therefore produces a **decrease** in backscatter, i.e. a **negative** log-ratio.
Water is selected where the log-ratio falls *below* the threshold, not above it.
Getting this backwards produces a mask of everything that is not flooded, which is
plausible-looking and completely wrong -- hence the explicit test for it.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


class ThresholdError(ValueError):
    """Raised when no separable threshold can be found."""


def log_ratio_db(
    pre_db: npt.NDArray[np.floating],
    post_db: npt.NDArray[np.floating],
) -> npt.NDArray[np.floating]:
    """Bi-temporal log-ratio of two decibel rasters.

    Both inputs must already be in decibels -- pass them through
    :func:`ml.sar.units.ensure_decibel` first. This function cannot check
    that for you, which is precisely why the scale is carried as declared metadata
    on :class:`~ml.contracts.scene.RasterSpec` rather than inferred.

    Returns
    -------
    numpy.ndarray
        ``post_db - pre_db``. Negative where backscatter decreased (candidate
        flooding), positive where it increased. ``NaN`` wherever either input was
        ``NaN``, so invalid pixels propagate rather than being silently treated as
        zero change.
    """
    if pre_db.shape != post_db.shape:
        raise ValueError(
            f"pre and post rasters must have identical shape, got "
            f"{pre_db.shape} and {post_db.shape}"
        )
    # NaN propagates naturally through subtraction, which is the behaviour we want:
    # a pixel that was invalid in either epoch has no valid change value.
    return (post_db.astype(np.float64) - pre_db.astype(np.float64)).astype(np.float32)


def otsu_threshold(
    values: npt.NDArray[np.floating],
    *,
    bins: int = 256,
    min_valid_fraction: float = 0.01,
) -> float:
    """Otsu's threshold: the value maximising between-class variance.

    Implemented directly rather than pulled from scikit-image so that this package
    keeps NumPy as its only numeric dependency and the whole suite runs offline.
    The algorithm is small and the test suite pins it against a synthetic bimodal
    distribution with a known answer.

    Reference: Otsu, N. (1979), "A threshold selection method from gray-level
    histograms", IEEE Transactions on Systems, Man, and Cybernetics 9(1), 62-66.

    Parameters
    ----------
    values
        Any-dimensional array. ``NaN`` entries are excluded.
    bins
        Histogram resolution. 256 matches the classical formulation and is ample
        for a dB-domain change image whose useful range spans tens of decibels.
    min_valid_fraction
        Refuse if fewer than this fraction of entries are finite. A change image
        that is almost entirely no-data cannot support a meaningful threshold, and
        computing one anyway would produce a confident mask from nothing.

    Returns
    -------
    float
        The threshold, in the units of ``values``.

    Raises
    ------
    ThresholdError
        If there are too few valid samples, or if the distribution is unimodal --
        i.e. the scene is entirely water or entirely land, or no change occurred.
        The caller is expected to translate this into a
        :attr:`~ml.contracts.outcome.AbstentionReason.NO_SEPARABLE_THRESHOLD`
        abstention rather than fabricating a mask.
    """
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ThresholdError("no finite values: cannot compute a threshold")

    valid_fraction = finite.size / values.size
    if valid_fraction < min_valid_fraction:
        raise ThresholdError(
            f"only {valid_fraction:.1%} of samples are valid "
            f"(minimum {min_valid_fraction:.1%}); refusing to threshold"
        )

    lo = float(finite.min())
    hi = float(finite.max())
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        raise ThresholdError(
            f"degenerate value range [{lo}, {hi}]: the distribution is unimodal, "
            "so no threshold separates two classes"
        )

    counts, edges = np.histogram(finite, bins=bins, range=(lo, hi))
    counts = counts.astype(np.float64)
    total = counts.sum()

    # Bin centres are the candidate thresholds.
    centres = (edges[:-1] + edges[1:]) / 2.0

    # Cumulative class-0 weight and mean at each split point.
    weight0 = np.cumsum(counts) / total
    # Guard the final entry: weight1 becomes 0 there and the variance term is 0/0.
    weight1 = 1.0 - weight0

    cumulative_mean = np.cumsum(counts * centres) / total
    global_mean = cumulative_mean[-1]

    # Between-class variance. Where a class is empty the expression is undefined;
    # np.errstate suppresses the warning and the resulting NaN is excluded below.
    with np.errstate(divide="ignore", invalid="ignore"):
        between = ((global_mean * weight0 - cumulative_mean) ** 2) / (weight0 * weight1)

    if not np.any(np.isfinite(between)):
        raise ThresholdError(
            "between-class variance is undefined everywhere: the distribution is "
            "unimodal, so no threshold separates two classes"
        )

    best = int(np.nanargmax(between))
    return float(centres[best])


def water_mask_from_change(
    change_db: npt.NDArray[np.floating],
    threshold_db: float,
) -> npt.NDArray[np.bool_]:
    """Select pixels whose backscatter *decreased* past the threshold.

    Water is dark in SAR, so flooding shows up as a negative log-ratio. Pixels are
    selected where ``change_db < threshold_db``.

    ``NaN`` entries evaluate ``False`` under the comparison, so invalid pixels are
    excluded from the mask automatically rather than being counted as water. That
    matters: counting no-data as water inflates the reported extent, which is a
    failure that biases in the alarming direction.
    """
    # Build the output array explicitly and return it, rather than returning the
    # value of np.less(). Two reasons: `out=` means this array *is* the result, so
    # naming it is clearer; and numpy's stubs type the ufunc call as Any, which the
    # repo's mypy settings (warn_return_any = true) correctly reject.
    mask: npt.NDArray[np.bool_] = np.zeros(change_db.shape, dtype=bool)
    with np.errstate(invalid="ignore"):
        # `where=` leaves non-finite positions untouched, so they keep the False
        # they were initialised with. NaN < x would be False anyway, but being
        # explicit means no-data can never be counted as water.
        np.less(change_db, threshold_db, where=np.isfinite(change_db), out=mask)
    return mask
