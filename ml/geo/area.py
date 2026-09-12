"""Area measurement -- the only place a user-visible area is produced.

House rule inherited from the earlier SatQuery work and kept deliberately:

    ``area_hectares`` is the only function permitted to emit a user-visible area.

One function to audit, one function to test, one place where the CRS guard lives.
If a second function in this codebase ever starts returning hectares, that is a
defect regardless of whether its arithmetic is correct, because it doubles the
surface that has to be reviewed for the project's central claim.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import numpy as np
import numpy.typing as npt

from ml.contracts.measurement import Measurement, MeasurementUnit
from ml.contracts.scene import SceneRef
from ml.geo.crs import assert_projected

#: Square metres in one hectare.
SQUARE_METRES_PER_HECTARE = 10_000.0

#: Fully-qualified name recorded in ``Measurement.produced_by``. Kept as a module
#: constant so the string cannot drift away from the function it names.
PRODUCER = "ml.geo.area.area_hectares"


def pixel_area_m2(pixel_size_m: tuple[float, float], crs: str) -> float:
    """Area of a single pixel in square metres.

    Parameters
    ----------
    pixel_size_m
        ``(x, y)`` pixel dimensions as positive magnitudes. A GeoTIFF affine
        transform normally carries a negative y step for north-up rasters; take
        ``abs()`` before calling.
    crs
        CRS the raster is in. Must be projected -- see
        :func:`ml.geo.crs.assert_projected`.

    Raises
    ------
    ml.geo.crs.CRSError
        If ``crs`` is geographic or unrecognised.
    ValueError
        If either pixel dimension is non-positive.
    """
    assert_projected(crs, operation="compute pixel area")

    x, y = pixel_size_m
    if x <= 0 or y <= 0:
        raise ValueError(f"pixel_size_m must be positive magnitudes, got {pixel_size_m!r}")
    return float(x) * float(y)


def area_hectares(
    mask: npt.NDArray[np.bool_] | npt.NDArray[np.integer],
    *,
    pixel_size_m: tuple[float, float],
    crs: str,
    derived_from: Sequence[SceneRef],
    code_version: str,
    name: str = "inundated_area",
) -> Measurement:
    """Measure the area covered by ``mask`` and return it with full provenance.

    Parameters
    ----------
    mask
        2-D boolean (or 0/1 integer) array. ``True`` / non-zero marks a pixel
        belonging to the feature being measured. Any invalid pixels must already
        have been excluded by the caller -- this function counts what it is given
        and does not know which pixels were no-data.
    pixel_size_m
        Pixel dimensions in metres, positive magnitudes.
    crs
        The CRS the mask is in. Must be projected; a geographic CRS raises.
    derived_from
        Scenes this measurement is derived from. Must be non-empty -- the returned
        ``Measurement`` cannot be constructed otherwise.
    code_version
        Version or commit SHA of this package, recorded so the number can be
        reproduced later.
    name
        Machine-readable measurement name recorded in the contract.

    Returns
    -------
    Measurement
        Area in hectares, carrying the producing function, code version, CRS and
        source scenes.

    Notes
    -----
    The value is converted through :class:`~decimal.Decimal` via ``str`` rather
    than directly from the float, so the stored figure is the decimal one a reader
    would write down rather than the nearest binary approximation to it. Quantised
    to one decimal place: a flood extent reported to a tenth of a hectare (100 m2)
    is already finer than the 10 m pixel grid justifies, and more digits would
    imply precision the measurement does not have.
    """
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2-D, got shape {mask.shape}")
    if len(derived_from) == 0:
        raise ValueError(
            "derived_from is empty: a measurement must name the observations it came from"
        )

    # assert_projected runs inside pixel_area_m2; calling it here as well would be
    # redundant. The guard is intentionally on the low-level function so that any
    # future caller of pixel_area_m2 inherits it.
    per_pixel_m2 = pixel_area_m2(pixel_size_m, crs)

    # np.count_nonzero rather than sum(): it is exact for both bool and integer
    # inputs and cannot accumulate floating-point error on large arrays.
    covered_pixels = int(np.count_nonzero(mask))
    hectares = (covered_pixels * per_pixel_m2) / SQUARE_METRES_PER_HECTARE

    return Measurement(
        name=name,
        value=Decimal(f"{hectares:.1f}"),
        unit=MeasurementUnit.HECTARES,
        produced_by=PRODUCER,
        code_version=code_version,
        crs=crs,
        derived_from=list(derived_from),
    )
