"""Canonical ML-facing contracts — the single source of truth for the whole repo.

Authority: P1 (Tech Lead / Backend Architect)
-----------------------------------------------
Both P3 (ml/contracts/) and P4 (packages/contracts/data.py) independently built
SceneRef models that are incompatible:

  P3  uses strict Enums, ``href``, ``frozen=True``, ``extra="forbid"``
  P4  uses plain strings, ``href``, adds ``cloud_cover``

This module is the reconciliation. It takes the best of both:

  * P3's strict Enum types for ``Provider`` and ``PassDirection`` (a string typo is
    a validation error, not a runtime crash halfway through a pipeline)
  * P3's ``frozen=True`` and ``extra="forbid"`` (validated provenance must not be
    mutable or extensible by accident)
  * P3's ``revalidate_instances="always"`` (a contract built before a validator was
    tightened cannot slip through when nested)
  * P4's ``cloud_cover`` field (needed by the eo-data search pipeline)
  * The field is named ``href`` — the canonical download URL for the asset,
    validated against the SSRF allowlist before use. ``href`` was P4's internal
    name; this is the cross-service name.

DO NOT import from ml.contracts or packages.contracts.data after this module
exists. Both of those are transitional and will be deleted once their owners
(P3 and P4) update their imports here.

P3's side of that is done
-------------------------
``ml/contracts/`` is deleted and every P3 module imports from here. Three things
had to come across for that to be possible, and all three are additive -- no
field, type, requiredness or enum member in this file changed, which was checked
by snapshotting ``model_fields`` before and after rather than by reading.

1. **The validators.** They did not survive the original transcription, so this
   file's models had the strict *config* -- frozen, extra="forbid",
   revalidate_instances -- and none of the strict *behaviour*. Measured against
   this file before the restore: hectares in EPSG:4326 constructed fine, so did a
   negative area, and so did a ``NOT_CALIBRATED`` confidence carrying a value of
   0.9. Each of those is a plausible wrong number arriving with full provenance
   attached, which makes it read as more credible rather than less. Restoring them
   completes what this module's own docstring already promised.

2. **The SAR vocabulary** -- ``Polarization``, ``BackscatterScale``,
   ``RasterSpec``, ``ScenePair``. The last one was already anticipated here: the
   ``SceneRef`` docstring above refers to ScenePair refusing to pair two scenes
   with unknown orbits, and now the class that does the refusing lives beside it.

3. **The prose.** ``MeasurementUnit``, ``AbstentionReason``, ``Abstention`` and
   ``Analysis`` were field-identical to P3's but had lost the comments explaining
   why each constraint exists. Those constraints are the point -- ``min_length=1``
   on ``measurements`` and ``scenes`` is what makes ``Analysis`` structurally
   unable to represent a fabricated result -- so the reasoning is back with them.

``crs_policy`` moved here for the same reason: ``Measurement`` enforces it, so it
has to be importable without ``packages/`` depending on ``ml/``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.contracts.crs_policy import explain_unsafe_for_area, is_area_safe

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Strict(BaseModel):
    """Immutable, allowlist-validated base for all contract objects.

    Identical to packages.contracts.Strict — copied here so that neither
    ml/ nor packages/ depends on the other.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        str_strip_whitespace=True,
        revalidate_instances="always",
    )


# ---------------------------------------------------------------------------
# Scene identity
# ---------------------------------------------------------------------------


class Provider(str, Enum):
    """Where a scene came from.

    Kept as a closed set so that an unknown provider is a validation error
    rather than an untracked data source appearing in provenance.
    """

    ASF_HYP3 = "asf_hyp3"
    COPERNICUS_DATASPACE = "copernicus_dataspace"
    PLANETARY_COMPUTER = "planetary_computer"
    BHOONIDHI = "bhoonidhi"
    SEN1FLOODS11 = "sen1floods11"
    SENFORFLOOD = "senforflood"


class PassDirection(str, Enum):
    """Orbit pass direction."""

    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"


class Polarization(str, Enum):
    """SAR polarisation channel.

    ``str`` mixin so values serialise as plain strings in JSON without a custom
    encoder, and so comparison against a raw string from a STAC response works.
    """

    VV = "VV"
    VH = "VH"
    HH = "HH"
    HV = "HV"


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


class SceneRef(Strict):
    """Identifies exactly one satellite observation.

    Every user-visible number must be traceable to at least one of these.
    There are no defaults: a SceneRef cannot be constructed without saying
    what it refers to.

    Field notes
    -----------
    ``href``
        Canonical download URL for the asset. Validated against the SSRF
        allowlist in services/inference before it is ever dereferenced.
        (Previously ``href`` in the P4 branch — renamed for clarity.)
    ``cloud_cover``
        Tile-level cloud cover percentage [0, 100]. Required by the eo-data
        search pipeline for optical filtering. None for SAR (cloud-blind).
    ``relative_orbit`` / ``pass_direction``
        Optional because not every provider exposes them, but ScenePair
        refuses to pair two scenes when either is missing.
    """

    provider: Provider
    collection: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    acquired_at: datetime
    platform: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    relative_orbit: int | None
    pass_direction: PassDirection | None
    href: str = Field(min_length=1)
    cloud_cover: float | None = Field(default=None, ge=0, le=100)


class AssetRef(Strict):
    """Metadata for a resolved and staged asset."""

    s3_uri: str
    titiler_url: str
    item_id: str
    asset_key: str


class Observation(Strict):
    """A normalized EO observation ready for the ML pipeline.

    ``assets`` maps a canonical asset key (e.g. ``"vh"``, ``"visual"``) to
    its download href. Every href must pass the SSRF allowlist check before
    use — validation is the caller's responsibility, not this model's.
    """

    observation_id: str = Field(min_length=1)
    scene: SceneRef
    geometry: dict  # GeoJSON geometry dict
    assets: dict[str, str]  # asset_key -> href
    normalized_properties: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Raster and pairing (harvested from P3's ml/contracts/scene.py)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Measurement & Analysis (harvested from P3's ml/contracts/)
# ---------------------------------------------------------------------------


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


PHYSICAL_UNITS: frozenset[MeasurementUnit] = frozenset(
    {
        MeasurementUnit.HECTARES,
        MeasurementUnit.SQUARE_KILOMETRES,
        MeasurementUnit.METRES,
        MeasurementUnit.KILOMETRES,
    }
)


class ConfidenceBasis(str, Enum):
    MODEL_AGREEMENT = "model_agreement"
    CALIBRATED_PROBABILITY = "calibrated_probability"
    NOT_CALIBRATED = "not_calibrated"


class Confidence(Strict):
    """A confidence value together with the evidence that justifies it."""

    basis: ConfidenceBasis
    value: Decimal | None
    interval: tuple[Decimal, Decimal] | None
    calibration_ref: str | None
    agreement_iou: Decimal | None
    caveats: tuple[str, ...]

    @model_validator(mode="after")
    def _value_requires_a_basis(self) -> "Confidence":
        """NOT_CALIBRATED means we do not have a number, so we must not print one."""
        if self.basis is ConfidenceBasis.NOT_CALIBRATED and self.value is not None:
            raise ValueError(
                "basis is NOT_CALIBRATED but a value was supplied; report None and "
                "let the UI say so, rather than printing an unjustified figure"
            )
        if self.basis is not ConfidenceBasis.NOT_CALIBRATED and self.value is None:
            raise ValueError(
                f"basis is {self.basis.value} but no value was supplied; either "
                "provide the value or declare NOT_CALIBRATED"
            )
        return self

    @model_validator(mode="after")
    def _calibrated_must_cite_its_calibration(self) -> "Confidence":
        """A calibrated probability that cannot point at its report is not one.

        Calibration is configuration-specific: a model calibrated on one sensor
        and resolution is not calibrated for another.
        """
        if self.basis is ConfidenceBasis.CALIBRATED_PROBABILITY and not self.calibration_ref:
            raise ValueError(
                "CALIBRATED_PROBABILITY requires calibration_ref pointing at the "
                "generated calibration report (ECE + reliability diagram)"
            )
        return self

    @model_validator(mode="after")
    def _agreement_basis_requires_agreement(self) -> "Confidence":
        if self.basis is ConfidenceBasis.MODEL_AGREEMENT and self.agreement_iou is None:
            raise ValueError(
                "basis is MODEL_AGREEMENT but agreement_iou is None; the agreement "
                "between the two methods IS the evidence, so it must be reported"
            )
        return self

    @model_validator(mode="after")
    def _fields_must_not_contradict_each_other(self) -> "Confidence":
        """Bound each field, then check they tell the same story.

        Every combination below was individually legal in an object that, read as
        a whole, contradicts itself: a MODEL_AGREEMENT confidence reporting 0.9
        beside an IoU of 0.5, or an interval that excludes its own point estimate.
        """
        for label, candidate in (("value", self.value), ("agreement_iou", self.agreement_iou)):
            if candidate is not None and not (Decimal(0) <= candidate <= Decimal(1)):
                raise ValueError(f"{label} must lie in [0, 1], got {candidate}")

        if self.interval is not None:
            low, high = self.interval
            if not (Decimal(0) <= low <= high <= Decimal(1)):
                raise ValueError(
                    f"interval must satisfy 0 <= low <= high <= 1, got {self.interval}"
                )
            if self.value is not None and not (low <= self.value <= high):
                raise ValueError(
                    f"value {self.value} lies outside its own interval [{low}, {high}]"
                )

        if (
            self.basis is ConfidenceBasis.MODEL_AGREEMENT
            and self.value is not None
            and self.agreement_iou is not None
            and self.value != self.agreement_iou
        ):
            raise ValueError(
                f"basis is MODEL_AGREEMENT so value is the agreement, but value "
                f"({self.value}) and agreement_iou ({self.agreement_iou}) differ"
            )
        return self

    @classmethod
    def not_calibrated(cls, *, caveats: tuple[str, ...] = ()) -> "Confidence":
        """The honest answer outside a fitted configuration, made the easy one."""
        return cls(
            basis=ConfidenceBasis.NOT_CALIBRATED,
            value=None,
            interval=None,
            calibration_ref=None,
            agreement_iou=None,
            caveats=tuple(caveats),
        )


class Measurement(Strict):
    """A single number a user may see, with everything needed to audit it."""

    name: str = Field(min_length=1)
    value: Decimal
    unit: MeasurementUnit
    produced_by: str = Field(min_length=1)
    code_version: str = Field(min_length=1)
    crs: str = Field(min_length=1)
    derived_from: tuple[SceneRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_an_area_safe_crs(self) -> "Measurement":
        """Refuse to express a physical extent measured somewhere it cannot be.

        The single most important guard in this file. Hectares computed in
        EPSG:4326 are wrong by a latitude-dependent factor; hectares computed in
        EPSG:3857 are inflated by 1/cos^2(latitude). Neither raises, both are
        internally consistent, and both survive review.

        A positive allowlist, not a blacklist of known-bad identifiers: the set of
        unsafe CRSs is unbounded and the set of safe ones is small and known.
        See packages/contracts/crs_policy.py.
        """
        if self.unit in PHYSICAL_UNITS and not is_area_safe(self.crs):
            raise ValueError(
                f"measurement {self.name!r} is in {self.unit.value} but was taken "
                f"in {self.crs}, which is not safe to measure in: "
                f"{explain_unsafe_for_area(self.crs)}. Reproject to the local UTM "
                "zone before measuring."
            )
        return self

    @model_validator(mode="after")
    def _reject_negative_value(self) -> "Measurement":
        """A negative area, length or count is always a bug, never data.

        COUNT is included: a count of pixels or detections is no more able to be
        negative than an area, and because a validated Measurement travels
        straight to the user, an impossible value arrives carrying full
        provenance -- which makes it read as more credible, not less.
        """
        countable = set(PHYSICAL_UNITS) | {MeasurementUnit.COUNT}
        if self.unit in countable and self.value < 0:
            raise ValueError(
                f"measurement {self.name!r} has negative value {self.value} for "
                f"unit {self.unit.value}"
            )
        return self

    @model_validator(mode="after")
    def _bound_fractions(self) -> "Measurement":
        if self.unit is MeasurementUnit.FRACTION and not (0 <= self.value <= 1):
            raise ValueError(
                f"measurement {self.name!r} is a fraction but has value {self.value}; "
                "fractions lie in [0, 1] -- a percentage was probably intended"
            )
        return self


class AbstentionReason(str, Enum):
    """Machine-readable reasons the subsystem may decline to answer.

    Deliberately a closed set: a new way of failing requires adding a member here,
    which forces a decision about how the UI should present it and gives the
    observability layer a stable label to count. A free-text reason would make the
    abstention-rate-by-reason dashboard -- the single most informative health
    signal this subsystem has -- useless.
    """

    #: No usable acquisition exists in the requested window.
    NO_SCENES_IN_WINDOW = "no_scenes_in_window"
    #: Optical is unusable and the question requires optical.
    CLOUD_EXCEEDS_THRESHOLD = "cloud_exceeds_threshold"
    #: The available sensor physically cannot answer the question asked
    #: (e.g. a spectral question under cloud -- SAR cannot substitute).
    SENSOR_CANNOT_ANSWER = "sensor_cannot_answer"
    #: Candidate scenes differ in relative orbit or pass direction.
    ORBIT_MISMATCH = "orbit_mismatch"
    #: The AOI falls outside the coverage of every available provider.
    AOI_OUTSIDE_COVERAGE = "aoi_outside_coverage"
    #: Provider holds the product offline (e.g. Bhoonidhi ``Online: "N"``), so it
    #: cannot be fetched through the API at all.
    PRODUCT_OFFLINE = "product_offline"
    #: The deterministic baseline and the learned model disagree beyond the
    #: configured threshold. Flagged rather than smoothed over.
    MODELS_DISAGREE = "models_disagree"
    #: AOI exceeds the resource bound; refused rather than attempted.
    AOI_TOO_LARGE = "aoi_too_large"
    #: Input failed preflight validation (bands, units, dtype, dimensions, CRS).
    INPUT_FAILED_PREFLIGHT = "input_failed_preflight"
    #: Otsu found no separable threshold -- the histogram is unimodal, meaning the
    #: scene is all water or all land, or the change signal is absent.
    NO_SEPARABLE_THRESHOLD = "no_separable_threshold"


class Abstention(Strict):
    """A declined answer, with enough detail to be actionable.

    ``scenes_seen`` matters: showing what was examined before declining is what
    distinguishes a considered refusal from a failure. A user who is told
    "no Sentinel-1 acquisition over this AOI between 12 and 26 August; nearest is
    3 September" can act. A user who is told "error" cannot.
    """

    outcome: Literal["abstained"] = "abstained"
    reason: AbstentionReason
    #: Human-readable explanation. Rendered from a template over the execution
    #: trace, never generated by a language model -- see the P3 audit, issue I-3.
    explanation: str = Field(min_length=1)
    #: Nearest date for which an answer would be possible, when one exists.
    nearest_usable: datetime | None
    #: Scenes that were examined before declining. May be empty when nothing was
    #: found at all, which is itself informative.
    scenes_seen: tuple[SceneRef, ...]
    trace_id: str = Field(min_length=1)


class Analysis(Strict):
    """A completed analysis.

    ``measurements`` and ``scenes`` both have ``min_length=1``: an analysis that
    measured nothing, or that cannot say which observations it used, is not an
    analysis. Those two constraints are what make this type unable to represent a
    fabricated result.

    ``confidence`` may be ``None`` -- see :mod:`packages.contracts.ml`.
    A missing confidence is honest; an invented one is not.

    ``degraded_from`` records when this result came from a fallback path (for
    example, the learned model timed out and the deterministic baseline produced
    this instead). It is surfaced to the user rather than hidden, because a result
    produced by a simpler method is still a real result but the reader should know.
    """

    outcome: Literal["analysed"] = "analysed"
    measurements: tuple[Measurement, ...] = Field(min_length=1)
    #: Object-storage key for the vectorised extent (GeoJSON).
    geometry_ref: str | None
    #: Object-storage keys for produced rasters (masks, composites).
    raster_refs: tuple[str, ...]
    confidence: Confidence | None
    scenes: tuple[SceneRef, ...] = Field(min_length=1)
    #: Name of the method that actually produced this, when a fallback was used.
    #: ``None`` means the primary path ran.
    degraded_from: str | None
    #: Plausibility flags carried up from postprocessing.
    caveats: tuple[str, ...]
    trace_id: str = Field(min_length=1)


#: Every analysis entry point returns this union and nothing else.
MissionOutcome = Annotated[Analysis | Abstention, Field(discriminator="outcome")]

__all__ = [
    "Strict",
    "Provider",
    "PassDirection",
    "Polarization",
    "BackscatterScale",
    "SceneRef",
    "AssetRef",
    "Observation",
    "RasterSpec",
    "ScenePair",
    "MeasurementUnit",
    "PHYSICAL_UNITS",
    "ConfidenceBasis",
    "Confidence",
    "Measurement",
    "AbstentionReason",
    "Abstention",
    "Analysis",
    "MissionOutcome",
]
