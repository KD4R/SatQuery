"""Assert an array is what it claims to be, before anything processes it.

Issue P3-02. This is the gate that turns "we assumed the data was in dB" into a
typed failure at the boundary rather than a wrong number at the end.

Lives beside the reader in ``ml/io/`` because these are data-quality checks on
arrays that ``read_raster`` has already produced. The href allowlist that used to
share this module is an access-control decision and moved to
``services/inference/validation.py`` at review (PR #17); the layering runs
``services -> ml -> packages``, so the analysis library cannot reach up to it.

Design note on the return type
------------------------------
Failures here do not raise past the service boundary -- they become an
:class:`~packages.contracts.Abstention` with reason ``INPUT_FAILED_PREFLIGHT``.
Internally a :class:`PreflightError` is raised so the offending check is easy to
locate, and the caller translates. That keeps "absence of an answer is a value,
not an exception" true at the API surface while keeping tracebacks useful inside
the package.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from packages.contracts import RasterSpec


class PreflightError(ValueError):
    """An input failed validation and must not be processed."""


def validate_against_spec(
    array: npt.NDArray[np.floating],
    actual: RasterSpec,
    expected: RasterSpec,
) -> None:
    """Assert that a loaded array matches both its own declared spec and what we need.

    Two comparisons happen here and they are different:

    1. ``array`` versus ``actual`` -- does the data match what the provider *said*
       it was? A mismatch means the metadata is wrong, which invalidates everything
       downstream including the scale declaration.
    2. ``actual`` versus ``expected`` -- is what the provider gave us what this
       model needs? A mismatch here is recoverable (reorder bands, convert scale);
       this function reports it rather than silently fixing it, so the conversion
       is an explicit, logged step.

    Raises
    ------
    PreflightError
        On any mismatch, with a message naming the specific field.
    """
    # --- 1. Data versus its own declared metadata -------------------------------
    expected_bands = len(actual.band_order)
    if array.ndim != 3:
        raise PreflightError(f"expected a 3-D (band, y, x) array, got shape {array.shape}")
    if array.shape[0] != expected_bands:
        raise PreflightError(
            f"declared band_order has {expected_bands} bands "
            f"{tuple(b.value for b in actual.band_order)} but array has "
            f"{array.shape[0]}"
        )
    if array.shape[1] != actual.height or array.shape[2] != actual.width:
        raise PreflightError(
            f"declared dimensions {actual.width}x{actual.height} do not match array "
            f"shape {array.shape[2]}x{array.shape[1]}"
        )
    if array.dtype.name != actual.dtype:
        raise PreflightError(
            f"declared dtype {actual.dtype!r} does not match array dtype " f"{array.dtype.name!r}"
        )

    # --- 2. Declared metadata versus what the model needs -----------------------
    if actual.band_order != expected.band_order:
        raise PreflightError(
            "band order mismatch: source provides "
            f"{tuple(b.value for b in actual.band_order)} but the model expects "
            f"{tuple(b.value for b in expected.band_order)}. Reorder explicitly; "
            "silently mismatching them normalises each channel with the other "
            "channel's statistics, which produces a plausible wrong answer rather "
            "than an error."
        )
    if actual.crs != expected.crs:
        raise PreflightError(f"CRS mismatch: source is {actual.crs}, model expects {expected.crs}")
    # Scale is intentionally *not* required to match: converting is legitimate and
    # is handled by ensure_decibel(). It is checked for being a known value only.
    if actual.scale is None:  # pragma: no cover - pydantic makes this unreachable
        raise PreflightError("source raster does not declare a backscatter scale")


def validate_finite_fraction(
    array: npt.NDArray[np.floating],
    *,
    minimum: float = 0.5,
    nodata: float | None = None,
) -> float:
    """Reject a raster that is mostly no-data, and report the valid fraction.

    A chip that is 90% no-data can still produce a mask and an area figure, and
    that figure will be confidently wrong because it describes a sliver of the AOI
    as though it described the whole thing.

    Parameters
    ----------
    nodata
        The declared no-data sentinel from :attr:`RasterSpec.nodata`, when it is a
        finite value rather than ``NaN``.

        Pass it. Checking only ``np.isfinite`` was the original behaviour and it
        fails open on exactly the rasters this function exists to catch: a chip
        filled entirely with ``-9999`` is 100% finite, reports a valid fraction of
        1.0, sails through this gate and then contributes 262,144 fabricated
        backscatter samples to an Otsu histogram. Providers that use a finite
        sentinel rather than ``NaN`` are common enough -- GeoTIFF has no NaN
        convention for integer bands -- that this cannot be treated as an edge case.

    Returns
    -------
    float
        The fraction of valid samples, so the caller can record it as a caveat
        even when it passes.
    """
    if array.size == 0:
        raise PreflightError("raster is empty")
    valid = np.isfinite(array)
    if nodata is not None and math.isfinite(nodata):
        valid &= array != nodata
    fraction = float(np.count_nonzero(valid) / array.size)
    if fraction < minimum:
        raise PreflightError(
            f"only {fraction:.1%} of samples are valid (minimum {minimum:.0%}); "
            "an area measured from this would describe a fraction of the AOI as "
            "though it described all of it"
        )
    return fraction
