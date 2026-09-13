"""The deterministic water-detection baseline.

What this is for
----------------
This is the path that works with no GPU, no labels and no training. It is not a
placeholder for the learned model and it is not deleted once one exists, for three
reasons:

  * it is the only path guaranteed to run on day one, so it is what the rest of the
    system integrates against while the model is still being trained;
  * it is the honest degraded mode. When the learned model fails, falling back here
    and *labelling the result as degraded* is a real answer, where a stored fixture
    would be a number no satellite produced;
  * agreement between two methods that fail differently is the only confidence
    signal available before calibration. A learned model with no independent
    baseline beside it is an unfalsifiable claim.

What it is honest about
-----------------------
Single-date Otsu on absolute backscatter is a weak detector, and this package has
measured that rather than assumed it either way -- see ADR-0007 D10. Otsu's
goodness-of-fit does not separate Sen1Floods11 chips containing water from chips
containing none, and the dataset authors' own Otsu baseline under-predicts badly on
chips where the hand labels mark half the scene as flooded.

So every ``Analysis`` produced here carries ``NOT_CALIBRATED`` confidence and a
caveat naming the method. The number is real, measured, and reproducible; what it
is not is trustworthy on its own, and the contract says so rather than leaving the
reader to infer it.

The bi-temporal path is the one with better physics behind it, because the
separable quantity is *change* rather than absolute brightness. It is blocked on a
provider that supplies pre-event imagery -- Sen1Floods11 has none -- which is issue
#14.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from packages.contracts import (
    Abstention,
    AbstentionReason,
    Analysis,
    Confidence,
    MissionOutcome,
    Polarization,
    SceneRef,
)
from packages.contracts.crs_policy import is_area_safe
from ml.geo.area import area_hectares, pixel_area_m2
from ml.pipeline.postprocess import DEFAULT_MIN_MAPPING_UNIT_HA, postprocess_water_mask
from ml.io.raster import Raster
from ml.io.preflight import PreflightError, validate_finite_fraction
from ml.sar.change import ThresholdError, otsu_threshold
from ml.sar.units import ensure_decibel

#: Water is dark in SAR. Flooding is therefore a *decrease* in backscatter and the
#: mask selects pixels BELOW the threshold. Inverting this yields a mask of
#: everything that is not flooded, which is plausible and entirely wrong, so the
#: direction is named here rather than left implicit in a comparison operator.
WATER_IS_BELOW_THRESHOLD = True

#: Minimum fraction of the chip that must carry real observations. Below this an
#: area figure describes a sliver of the AOI as though it described the whole.
DEFAULT_MIN_VALID_FRACTION = 0.5


@dataclass(frozen=True)
class Detection:
    """A water mask and the numbers behind it.

    Exists so that evaluation can score the *same* mask the pipeline reports,
    rather than recomputing one from the same primitives and hoping the two stay
    in step. Two implementations of one rule is how they drift.
    """

    mask: npt.NDArray[np.bool_]
    threshold_db: float
    valid_fraction: float


def water_mask_single_date(
    raster: Raster,
    *,
    polarization: Polarization = Polarization.VV,
    min_valid_fraction: float = DEFAULT_MIN_VALID_FRACTION,
) -> Detection:
    """Threshold one scene into a water mask. Raises rather than abstaining.

    The raising half of :func:`detect_water_single_date`, split out so that both
    the pipeline and the evaluation harness go through one implementation. The
    pipeline translates the exceptions into typed abstentions; a caller that wants
    the mask itself handles them directly.

    Unlike the pipeline entry point this does **not** require an area-safe CRS,
    because no area is computed here -- a mask is grid-agnostic. That matters for
    evaluation, which scores against labels on the source grid.
    """
    band = raster.band(polarization)

    # Declared scale in, decibels out. Never inspects values -- ADR-0007 D3.
    decibels = ensure_decibel(band, raster.spec.scale)

    valid_fraction = validate_finite_fraction(
        decibels, minimum=min_valid_fraction, nodata=raster.spec.nodata
    )
    threshold_db = otsu_threshold(decibels)

    # NaN compares False, so invalid pixels fall out of the mask rather than
    # counting as water. That direction matters: counting no-data as water inflates
    # the reported extent, and an error that over-reports a flood is the one most
    # likely to be acted on.
    mask: npt.NDArray[np.bool_] = np.zeros(decibels.shape, dtype=bool)
    with np.errstate(invalid="ignore"):
        np.less(decibels, threshold_db, where=np.isfinite(decibels), out=mask)

    return Detection(mask=mask, threshold_db=threshold_db, valid_fraction=valid_fraction)


def detect_water_single_date(
    raster: Raster,
    *,
    scenes: Sequence[SceneRef],
    code_version: str,
    polarization: Polarization = Polarization.VV,
    permanent_water: npt.NDArray[np.bool_] | None = None,
    min_valid_fraction: float = DEFAULT_MIN_VALID_FRACTION,
    min_mapping_unit_ha: float = DEFAULT_MIN_MAPPING_UNIT_HA,
    trace_id: str,
) -> MissionOutcome:
    """Threshold one SAR scene into open water, and measure it.

    Returns ``Analysis | Abstention``. There is no third outcome and no empty
    result with zeroed values: if the scene cannot support an answer, the
    abstention says which of ten machine-readable reasons applies.

    Parameters
    ----------
    raster
        Must already be in an area-safe CRS -- call
        :func:`ml.io.raster.reproject_to_area_safe_crs` first. Reprojection is not
        done here on purpose: the raster must be resampled bilinearly *before*
        thresholding, whereas a mask would need nearest-neighbour, and doing it in
        the wrong order silently smears the mask edges. Keeping the two steps
        separate makes the ordering impossible to get wrong.
    permanent_water
        Optional mask of water that is always there -- a river, a reservoir. It is
        subtracted, because a permanent lake reported as flooding is the single
        most embarrassing failure this pipeline can have, and it is guaranteed to
        happen on every scene containing one.
    """
    if not is_area_safe(raster.spec.crs):
        return Abstention(
            outcome="abstained",
            reason=AbstentionReason.INPUT_FAILED_PREFLIGHT,
            explanation=(
                f"raster is in {raster.spec.crs}, which is not safe to measure area "
                "in. Reproject to the local UTM zone before detection "
                "(ml.io.raster.reproject_to_area_safe_crs)."
            ),
            nearest_usable=None,
            scenes_seen=tuple(scenes),
            trace_id=trace_id,
        )

    try:
        detection = water_mask_single_date(
            raster, polarization=polarization, min_valid_fraction=min_valid_fraction
        )
    except PreflightError as error:
        return Abstention(
            outcome="abstained",
            reason=AbstentionReason.INPUT_FAILED_PREFLIGHT,
            explanation=str(error),
            nearest_usable=None,
            scenes_seen=tuple(scenes),
            trace_id=trace_id,
        )
    except ThresholdError as error:
        return Abstention(
            outcome="abstained",
            reason=AbstentionReason.NO_SEPARABLE_THRESHOLD,
            explanation=str(error),
            nearest_usable=None,
            scenes_seen=tuple(scenes),
            trace_id=trace_id,
        )

    mask = detection.mask
    threshold_db = detection.threshold_db
    valid_fraction = detection.valid_fraction

    caveats = [
        f"single-date Otsu on {polarization.value}; threshold {threshold_db:.2f} dB",
        (
            "method is a deterministic baseline, not a calibrated detector: Otsu "
            "separability does not distinguish flooded from unflooded scenes on "
            "Sen1Floods11 (ADR-0007 D10)"
        ),
    ]

    if valid_fraction < 1.0:
        caveats.append(f"{1.0 - valid_fraction:.1%} of the chip is no-data and was excluded")

    # Clean the raw threshold mask before anything measures it. A thresholded scene
    # is a map of everything darker than a number, which includes speckle, radar
    # shadow, smooth tarmac and every river that was there before the event.
    try:
        cleaned = postprocess_water_mask(
            mask,
            pixel_area_m2=pixel_area_m2(raster.spec.pixel_size_m, raster.spec.crs),
            permanent_water=permanent_water,
            min_mapping_unit_ha=min_mapping_unit_ha,
        )
    except ValueError as error:
        return Abstention(
            outcome="abstained",
            reason=AbstentionReason.INPUT_FAILED_PREFLIGHT,
            explanation=str(error),
            nearest_usable=None,
            scenes_seen=tuple(scenes),
            trace_id=trace_id,
        )

    mask = cleaned.mask
    caveats.extend(cleaned.caveats)

    # An empty mask after cleaning is a real answer -- "no flood detected here" --
    # not a failure, so it measures 0 ha rather than abstaining. Abstention means
    # the question could not be answered; this one was.

    measurement = area_hectares(
        mask,
        pixel_size_m=raster.spec.pixel_size_m,
        crs=raster.spec.crs,
        derived_from=tuple(scenes),
        code_version=code_version,
    )

    return Analysis(
        outcome="analysed",
        measurements=(measurement,),
        geometry_ref=None,
        raster_refs=(),
        # NOT_CALIBRATED is the honest basis and the easy one to reach, which is
        # the point of Confidence.not_calibrated() existing. A softmax or an Otsu
        # margin dressed up as a probability would be the same class of defect as
        # a fabricated hectare figure.
        confidence=Confidence.not_calibrated(
            caveats=("deterministic baseline; no calibration report exists for it",)
        ),
        scenes=tuple(scenes),
        degraded_from=None,
        caveats=tuple(caveats),
        trace_id=trace_id,
    )
