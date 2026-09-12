"""Canonical ML-facing contracts — the single source of truth for the whole repo.

Authority: P1 (Tech Lead / Backend Architect)
-----------------------------------------------
Both P3 (ml/contracts/) and P4 (packages/contracts/data.py) independently built
SceneRef models that are incompatible:

  P3  uses strict Enums, ``href``, ``frozen=True``, ``extra="forbid"``
  P4  uses plain strings, ``stac_href``, adds ``cloud_cover``

This module is the reconciliation. It takes the best of both:

  * P3's strict Enum types for ``Provider`` and ``PassDirection`` (a string typo is
    a validation error, not a runtime crash halfway through a pipeline)
  * P3's ``frozen=True`` and ``extra="forbid"`` (validated provenance must not be
    mutable or extensible by accident)
  * P3's ``revalidate_instances="always"`` (a contract built before a validator was
    tightened cannot slip through when nested)
  * P4's ``cloud_cover`` field (needed by the eo-data search pipeline)
  * The field is named ``href`` — the canonical download URL for the asset,
    validated against the SSRF allowlist before use. ``stac_href`` was P4's internal
    name; this is the cross-service name.

DO NOT import from ml.contracts or packages.contracts.data after this module
exists. Both of those are transitional and will be deleted once their owners
(P3 and P4) update their imports here.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Strict(BaseModel):
    """Immutable, allowlist-validated base for all contract objects.

    Identical to ml.contracts.base.Strict — copied here so that neither
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
        (Previously ``stac_href`` in the P4 branch — renamed for clarity.)
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
# Measurement & Analysis (harvested from P3's ml/contracts/)
# ---------------------------------------------------------------------------


class MeasurementUnit(str, Enum):
    """Units a measurement may be expressed in."""

    HECTARES = "ha"
    SQUARE_KILOMETRES = "km2"
    METRES = "m"
    KILOMETRES = "km"
    COUNT = "count"
    FRACTION = "fraction"


PHYSICAL_UNITS = frozenset(
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


class Measurement(Strict):
    """A single number a user may see, with everything needed to audit it."""

    name: str = Field(min_length=1)
    value: Decimal
    unit: MeasurementUnit
    produced_by: str = Field(min_length=1)
    code_version: str = Field(min_length=1)
    crs: str = Field(min_length=1)
    derived_from: tuple[SceneRef, ...] = Field(min_length=1)


class AbstentionReason(str, Enum):
    NO_SCENES_IN_WINDOW = "no_scenes_in_window"
    CLOUD_EXCEEDS_THRESHOLD = "cloud_exceeds_threshold"
    SENSOR_CANNOT_ANSWER = "sensor_cannot_answer"
    ORBIT_MISMATCH = "orbit_mismatch"
    AOI_OUTSIDE_COVERAGE = "aoi_outside_coverage"
    PRODUCT_OFFLINE = "product_offline"
    MODELS_DISAGREE = "models_disagree"
    AOI_TOO_LARGE = "aoi_too_large"
    INPUT_FAILED_PREFLIGHT = "input_failed_preflight"
    NO_SEPARABLE_THRESHOLD = "no_separable_threshold"


class Abstention(Strict):
    """A declined answer, with enough detail to be actionable."""

    outcome: Literal["abstained"] = "abstained"
    reason: AbstentionReason
    explanation: str = Field(min_length=1)
    nearest_usable: datetime | None
    scenes_seen: tuple[SceneRef, ...]
    trace_id: str = Field(min_length=1)


class Analysis(Strict):
    """A completed analysis."""

    outcome: Literal["analysed"] = "analysed"
    measurements: tuple[Measurement, ...] = Field(min_length=1)
    geometry_ref: str | None
    raster_refs: tuple[str, ...]
    confidence: Confidence | None
    scenes: tuple[SceneRef, ...] = Field(min_length=1)
    degraded_from: str | None
    caveats: tuple[str, ...]
    trace_id: str = Field(min_length=1)


#: Every analysis entry point returns this union and nothing else.
MissionOutcome = Annotated[Analysis | Abstention, Field(discriminator="outcome")]

__all__ = [
    "Strict",
    "Provider",
    "PassDirection",
    "SceneRef",
    "Observation",
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
