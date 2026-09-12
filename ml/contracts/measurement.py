"""The only shape a user-visible number is allowed to take.

Design rule
-----------
    A number without provenance is not a number, it is a rumour.

``Measurement`` cannot be constructed without naming (a) the function that produced
it, (b) the version of the code that function lived in, (c) the CRS the measurement
was taken in, and (d) at least one scene it was derived from. There are no defaults
on any of those fields, so the 2 a.m. shortcut -- returning a bare float because the
screen needs something in it -- fails at construction rather than shipping.

This is the type-system version of the house rule inherited from the earlier
SatQuery work: ``area_hectares`` is the only function permitted to emit a
user-visible area. Here that rule generalises -- every metric has exactly one
producing function, and it must say so.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import Field, model_validator

from ml.contracts.base import Strict
from ml.crs_policy import GEOGRAPHIC_CRS, explain_unsafe_for_area, is_area_safe
from ml.contracts.scene import SceneRef

#: ``GEOGRAPHIC_CRS`` is re-exported from :mod:`ml.crs_policy`, which owns the CRS
#: policy for the whole package, so that existing importers keep working. The guard
#: below no longer tests against it -- see the note in that module on why a
#: blacklist is the wrong shape for a safety check.
__all__ = ["GEOGRAPHIC_CRS", "Measurement", "MeasurementUnit", "PHYSICAL_UNITS"]


class MeasurementUnit(str, Enum):
    """Units a measurement may be expressed in.

    Split deliberately into physical units (which require a projected CRS) and
    dimensionless ones (which do not). ``_reject_geographic_crs`` relies on this
    distinction.
    """

    HECTARES = "ha"
    SQUARE_KILOMETRES = "km2"
    METRES = "m"
    KILOMETRES = "km"
    #: Dimensionless: a plain count of things, e.g. number of polygons.
    COUNT = "count"
    #: Dimensionless: a ratio in [0, 1], e.g. water fraction.
    FRACTION = "fraction"


#: Units that describe a physical extent on the ground and therefore may only be
#: measured in a projected coordinate reference system.
PHYSICAL_UNITS = frozenset(
    {
        MeasurementUnit.HECTARES,
        MeasurementUnit.SQUARE_KILOMETRES,
        MeasurementUnit.METRES,
        MeasurementUnit.KILOMETRES,
    }
)


class Measurement(Strict):
    """A single number a user may see, with everything needed to audit it.

    ``value`` is a :class:`~decimal.Decimal` rather than a float so that a figure
    quoted in a report is exactly the figure that was computed. Binary floats
    round-trip badly through JSON and through humans; a flood extent that reads
    ``4127.599999999999`` in one place and ``4127.6`` in another invites exactly the
    question this project exists to avoid.

    Parameters
    ----------
    name
        Stable machine-readable identifier, e.g. ``"inundated_area"``. Consumers
        (P2 evidence assembly) match on this, so it is part of the contract.
    produced_by
        Fully-qualified name of the single function that produced this value, e.g.
        ``"ml.geo.area.area_hectares"``. One function to audit, one
        function to test.
    code_version
        Version or commit SHA of the package that function lived in, so a number in
        an old report can be reproduced.
    crs
        The CRS the measurement was taken in. For physical units this must be a
        projected CRS -- enforced below.
    derived_from
        The scenes this number came from. Never empty.
    """

    name: str = Field(min_length=1)
    value: Decimal
    unit: MeasurementUnit
    produced_by: str = Field(min_length=1)
    code_version: str = Field(min_length=1)
    crs: str = Field(min_length=1)
    derived_from: tuple[SceneRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_geographic_crs(self) -> Measurement:
        """Refuse to express a physical extent measured in degrees.

        Degrees are not metres, and the error is not a constant -- one degree of
        longitude is about 111 km at the equator and about 78 km at 45 degrees
        north. An area computed in EPSG:4326 is therefore wrong by a factor that
        moves with latitude, which is the worst kind of wrong: internally
        consistent, plausible, and different for every AOI.

        Reprojection to a local UTM zone must happen *before* measurement. See
        :func:`ml.geo.crs.utm_epsg_for`.
        """
        if self.unit in PHYSICAL_UNITS and not is_area_safe(self.crs):
            raise ValueError(
                f"measurement {self.name!r} is in {self.unit.value} but was taken in "
                f"{self.crs}, which is not safe to measure in: "
                f"{explain_unsafe_for_area(self.crs)}. Reproject to the local UTM "
                "zone before measuring (see ml.geo.crs.utm_epsg_for)."
            )
        return self

    @model_validator(mode="after")
    def _reject_negative_value(self) -> Measurement:
        """A negative area, length or count is always a bug, never data.

        COUNT was originally outside this check, on the reasoning that the guard
        was about physical extents. But a count of pixels, scenes or detections is
        no more able to be negative than an area is, and because a validated
        ``Measurement`` travels straight into an ``Analysis`` and out to the user,
        an impossible value arrives carrying full provenance -- which makes it more
        credible, not less.

        FRACTION is excluded here only because it has a tighter check of its own
        below, bounding it to [0, 1].
        """
        countable = set(PHYSICAL_UNITS) | {MeasurementUnit.COUNT}
        if self.unit in countable and self.value < 0:
            raise ValueError(
                f"measurement {self.name!r} has negative value {self.value} "
                f"for unit {self.unit.value}"
            )
        return self

    @model_validator(mode="after")
    def _bound_fractions(self) -> Measurement:
        """A fraction outside [0, 1] means a denominator went wrong somewhere."""
        if self.unit is MeasurementUnit.FRACTION and not (Decimal(0) <= self.value <= Decimal(1)):
            raise ValueError(
                f"measurement {self.name!r} is a fraction but has value {self.value}, "
                "which is outside [0, 1]"
            )
        return self
