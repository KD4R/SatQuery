"""Scene identity and raster input contracts.

Why this module exists
----------------------
The two most expensive defects available to a SAR pipeline are both *silent* --
they produce a plausible number rather than an exception:

1. **Unit mismatch.** Sen1Floods11 training chips are stored in decibels. A live
   provider scene may be delivered in linear power. Run the same preprocessing on
   both and one of them is wrong by a logarithm. Nothing crashes; the mask looks
   reasonable; the hectare figure is simply incorrect.

2. **Band-order mismatch.** Two bands of the same dtype and shape are freely
   interchangeable to every tool in the stack, so swapping them normalises each
   channel with the other channel's mean and standard deviation. Again: no crash,
   wrong answer. Note that published descriptions of Sen1Floods11 disagree with
   the files themselves on this point -- see the reference below -- which is
   precisely why the order is declared rather than assumed.

Both are therefore represented as *declared, validated data* rather than as
conventions living in someone's head. Nothing downstream is permitted to guess.

Sen1Floods11 conventions, MEASURED from the v1.1 hand-labelled chips rather
than taken from the documentation (see docs/adr/ADR-0007, D3):
    - S1 layer: 2 bands, Float32, band order **VV (0) then VH (1)**, units
      decibels. The GeoTIFF band descriptions read ('VV', 'VH') on every chip
      inspected, and band 0 sits ~6 dB above band 1 throughout, which is the
      physical signature of co-polarised versus cross-polarised backscatter.
      Some secondary descriptions of this dataset state VH-then-VV; they
      disagree with the files. Trust the files.
    - Label layer: 1 band, Int16, encoding -1 no-data / 0 not-water / 1 water
    - Chips: 512 x 512, EPSG:4326 at 8.983e-05 deg -- **geographic, not
      projected**, so reprojection is mandatory before any area measurement
    Repository: https://github.com/cloudtostreet/Sen1Floods11
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field, model_validator

from ml.contracts.base import Strict


class Polarization(str, Enum):
    """SAR polarisation channel.

    ``str`` mixin so values serialise as plain strings in JSON without a custom
    encoder, and so comparison against a raw string from a STAC response works.
    """

    VV = "VV"
    VH = "VH"
    HH = "HH"
    HV = "HV"


class PassDirection(str, Enum):
    """Orbit pass direction.

    Sentinel-1 is side-looking. Two acquisitions from different pass directions
    see the same ground from different geometry, so any "change" measured between
    them includes the change in viewing angle. See :class:`ScenePair`.
    """

    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"


class BackscatterScale(str, Enum):
    """The scale a SAR raster's pixel values are expressed in.

    ASF HyP3 lets the requester choose this explicitly when ordering an RTC
    product (power is their default, decibel and amplitude are also offered), which
    is the main reason this project prefers ASF for the live path: the ambiguity is
    removed at the point of ordering rather than guessed at read time.

    Reference: ASF HyP3 Sentinel-1 RTC Product Guide,
    https://hyp3-docs.asf.alaska.edu/guides/rtc_product_guide/
    """

    #: Linear power (gamma-nought or sigma-nought). Values sit very close to zero.
    POWER = "POWER"
    #: Square root of power.
    AMPLITUDE = "AMPLITUDE"
    #: 10 * log10(power). What Sen1Floods11 chips are stored in.
    DECIBEL = "DECIBEL"


class Provider(str, Enum):
    """Where a scene came from.

    Kept as a closed set so that an unknown provider is a validation error rather
    than an untracked data source appearing in provenance.
    """

    ASF_HYP3 = "asf_hyp3"
    COPERNICUS_DATASPACE = "copernicus_dataspace"
    PLANETARY_COMPUTER = "planetary_computer"
    BHOONIDHI = "bhoonidhi"
    #: Research datasets used for training and evaluation, never for user-facing
    #: analysis. Kept in the same enum so provenance can record them honestly.
    SEN1FLOODS11 = "sen1floods11"
    SENFORFLOOD = "senforflood"


class SceneRef(Strict):
    """Identifies exactly one satellite observation.

    Every user-visible number must be traceable to at least one of these. There
    are no defaults: a ``SceneRef`` cannot be constructed without saying what it
    refers to.

    ``relative_orbit`` and ``pass_direction`` are optional because not every
    provider exposes them, but :class:`ScenePair` refuses to pair two scenes when
    either is missing -- absence blocks comparison rather than being assumed away.
    """

    provider: Provider
    collection: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    acquired_at: datetime
    platform: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    relative_orbit: int | None
    pass_direction: PassDirection | None
    #: Where the asset can be fetched from. Validated against an allowlist by the
    #: preflight stage before it is ever dereferenced (SSRF control owned by P3).
    href: str = Field(min_length=1)


class RasterSpec(Strict):
    """The declared properties of a raster about to enter the pipeline.

    This is the object the preflight stage asserts against. It carries everything
    needed to decide whether an array can be processed safely, and in particular it
    carries ``scale`` and ``band_order`` explicitly so that neither is inferred.

    ``crs`` is the storage CRS. It is *not* necessarily the CRS anything is
    measured in -- see :mod:`ml.geo.area`, which refuses to measure area
    in a geographic CRS regardless of what the source was stored in.
    """

    band_order: tuple[Polarization, ...] = Field(min_length=1)
    scale: BackscatterScale
    #: NumPy dtype name, e.g. "float32". Compared as a string so this contract does
    #: not depend on NumPy being importable wherever it is validated.
    dtype: str = Field(min_length=1)
    crs: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    #: Pixel size in metres as (x, y). Required even when the storage CRS is
    #: geographic, because area measurement needs it after reprojection.
    pixel_size_m: tuple[float, float]
    #: Sentinel value marking invalid pixels, or ``None`` when NaN is used.
    nodata: float | None

    @model_validator(mode="after")
    def _reject_duplicate_bands(self) -> RasterSpec:
        """A band appearing twice means the caller has confused band order."""
        if len(set(self.band_order)) != len(self.band_order):
            raise ValueError(f"band_order contains duplicates: {self.band_order}")
        return self

    @model_validator(mode="after")
    def _reject_nonpositive_pixel_size(self) -> RasterSpec:
        """Zero or negative pixel size would silently produce a zero or negative area.

        Note that a negative y pixel size is a perfectly normal thing to find in a
        GeoTIFF affine transform (north-up rasters have a negative y step). We take
        the magnitude at the point of reading; by the time a spec reaches here the
        value is expected to be a physical size, so it must be positive.
        """
        x, y = self.pixel_size_m
        if x <= 0 or y <= 0:
            raise ValueError(
                f"pixel_size_m must be positive magnitudes, got {self.pixel_size_m!r}; "
                "take abs() of the affine transform steps before constructing this spec"
            )
        return self


class ScenePair(Strict):
    """A pre-event / post-event pair for bi-temporal change detection.

    Encodes the rule that costs teams a week when it is left implicit:

        **Same relative orbit and same pass direction, or do not compare.**

    Sentinel-1 looks sideways. Two acquisitions from different relative orbits view
    the same ground at different incidence angles, so the backscatter difference
    between them contains a geometry term that has nothing to do with what happened
    on the ground. A flood-extent number computed from a mismatched pair is not a
    noisy measurement, it is a measurement of the wrong thing.

    Rather than warn, this refuses to construct. Callers catch the error and return
    an ``ORBIT_MISMATCH`` abstention -- absence of a valid comparison is a result,
    not a crash.
    """

    pre: SceneRef
    post: SceneRef

    @model_validator(mode="after")
    def _require_comparable_geometry(self) -> ScenePair:
        if self.pre.relative_orbit is None or self.post.relative_orbit is None:
            raise ValueError(
                "cannot pair scenes with unknown relative_orbit: "
                f"pre={self.pre.item_id} post={self.post.item_id}. "
                "Unknown geometry blocks comparison; it is not assumed to match."
            )
        if self.pre.relative_orbit != self.post.relative_orbit:
            raise ValueError(
                "relative_orbit mismatch "
                f"({self.pre.relative_orbit} vs {self.post.relative_orbit}): "
                "different orbits observe different geometry, so the measured "
                "change would include the change in viewing angle"
            )
        if self.pre.pass_direction is None or self.post.pass_direction is None:
            raise ValueError(
                "cannot pair scenes with unknown pass_direction: "
                f"pre={self.pre.item_id} post={self.post.item_id}"
            )
        if self.pre.pass_direction != self.post.pass_direction:
            raise ValueError(
                "pass_direction mismatch "
                f"({self.pre.pass_direction.value} vs {self.post.pass_direction.value})"
            )
        return self

    @model_validator(mode="after")
    def _require_chronological_order(self) -> ScenePair:
        """``pre`` must actually precede ``post``.

        Swapping them inverts the sign of the log-ratio, which turns a flood into a
        drying event. That is a plausible-looking wrong answer, so it is rejected.
        """
        if self.pre.acquired_at >= self.post.acquired_at:
            raise ValueError(
                "pre scene must be acquired strictly before post scene "
                f"({self.pre.acquired_at.isoformat()} >= "
                f"{self.post.acquired_at.isoformat()})"
            )
        return self
