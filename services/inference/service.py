"""Run one analysis: href in, `Analysis | Abstention` out.

This is the layer that decides *which method ran* and makes sure the answer says
so. The pipeline modules in `ml/` do the work; this chooses between them and
records the choice.

Three outcomes, and only three
-------------------------------
1. The learned model ran. `Analysis` with the model named in `produced_by`.
2. The learned model was unavailable, so the deterministic baseline ran.
   `Analysis` with `degraded_from` naming the model that could not run.
3. The scene could not support an answer. `Abstention` with a machine-readable
   reason.

There is no fourth. In particular there is no empty result with zeroed values and
no stored fixture — ADR-0007 D7. A degraded answer is honest because it is
labelled; an unlabelled one is a number pretending to be something it is not.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import rasterio

from packages.contracts import (
    Abstention,
    AbstentionReason,
    Analysis,
    BackscatterScale,
    Confidence,
    MissionOutcome,
    Polarization,
    SceneRef,
)
from ml.geo.area import area_hectares, pixel_area_m2
from ml.io.preflight import PreflightError
from ml.io.raster import Raster, RasterReadError, read_raster, reproject_to_area_safe_crs
from ml.pipeline.baseline import detect_water_single_date, water_mask_single_date
from ml.pipeline.learned import predict_water_mask
from ml.pipeline.postprocess import postprocess_water_mask
from ml.sar.change import ThresholdError
from services.inference.registry import BASELINE_METHOD, ModelRegistry, ModelUnavailable
from services.inference.sources import RasterSource

logger = logging.getLogger(__name__)

#: Band order the models were trained on. Declared, cross-checked at read time
#: against the file's own descriptions, never inferred -- ADR-0007 D3.
MODEL_BANDS = (Polarization.VV, Polarization.VH)

#: Probability above which a pixel is called water. 0.5 was swept against the
#: held-out set and is near-optimal (D14); it is a constant rather than a request
#: field because a caller tuning it per request would be tuning the reported area.
WATER_THRESHOLD = 0.5


@dataclass(frozen=True)
class AnalysisService:
    """Chooses a method, runs it, and labels what it did."""

    registry: ModelRegistry
    source: RasterSource
    code_version: str

    def analyse(
        self,
        *,
        scene: SceneRef,
        scene_href: str,
        trace_id: str,
        permanent_water_href: str | None = None,
        model_name: str | None = None,
        min_mapping_unit_ha: float = 0.5,
    ) -> MissionOutcome:
        try:
            raster = self._load(scene_href)
        except (PreflightError, RasterReadError) as error:
            return self._abstain(
                AbstentionReason.INPUT_FAILED_PREFLIGHT, str(error), scene, trace_id
            )

        permanent_water = None
        if permanent_water_href is not None:
            try:
                permanent_water = self._load_permanent_water(permanent_water_href, raster)
            except (PreflightError, RasterReadError) as error:
                return self._abstain(
                    AbstentionReason.INPUT_FAILED_PREFLIGHT,
                    f"permanent-water layer: {error}",
                    scene,
                    trace_id,
                )

        # An explicit request for the baseline is honoured without complaint. It is
        # a legitimate thing to ask for -- it is the comparison every claim is made
        # against -- so it is not treated as degradation.
        if model_name == "baseline":
            return detect_water_single_date(
                raster,
                scenes=[scene],
                code_version=self.code_version,
                permanent_water=permanent_water,
                min_mapping_unit_ha=min_mapping_unit_ha,
                trace_id=trace_id,
            )

        requested = model_name or self.registry.default()
        if requested is None:
            return self._degraded(
                raster,
                scene=scene,
                trace_id=trace_id,
                permanent_water=permanent_water,
                min_mapping_unit_ha=min_mapping_unit_ha,
                reason=(
                    "no registered model beats the deterministic baseline on "
                    "held-out regions, so the baseline was used"
                ),
                degraded_from=None,
            )

        try:
            model, normalisation, card = self.registry.load(requested)
        except ModelUnavailable as error:
            logger.warning("falling back to the baseline: %s", error)
            return self._degraded(
                raster,
                scene=scene,
                trace_id=trace_id,
                permanent_water=permanent_water,
                min_mapping_unit_ha=min_mapping_unit_ha,
                reason=str(error),
                degraded_from=requested,
            )

        try:
            mask = self._predict(model, normalisation, raster, permanent_water)
        except Exception as error:  # noqa: BLE001 -- see comment
            # Deliberately broad. Anything the model does wrong at inference time
            # is a reason to fall back to a working method, not a reason to fail
            # the request: the baseline is always available and always honest
            # about being the baseline. Narrowing this would mean listing every
            # way torch can fail, and being wrong about one of them costs an
            # answer the caller could have had.
            logger.exception("model %s failed at inference; using the baseline", requested)
            return self._degraded(
                raster,
                scene=scene,
                trace_id=trace_id,
                permanent_water=permanent_water,
                min_mapping_unit_ha=min_mapping_unit_ha,
                reason=f"model {requested!r} raised at inference: {error}",
                degraded_from=requested,
            )

        return self._measure(
            mask,
            raster=raster,
            scene=scene,
            trace_id=trace_id,
            permanent_water=permanent_water,
            min_mapping_unit_ha=min_mapping_unit_ha,
            produced_by=f"{card.name}@{card.version}",
            caveats=self._model_caveats(card),
            degraded_from=None,
        )

    # -- loading ------------------------------------------------------------- #

    def _load(self, href: str) -> Raster:
        """Resolve, read and reproject. Reprojection first, always.

        Area measured in a geographic CRS is wrong by a latitude-dependent factor,
        so the raster is put into its local UTM zone before anything measures it.
        Doing it here rather than inside the pipeline keeps the ordering explicit:
        backscatter is resampled bilinearly, a mask would need nearest, and the
        two must not be confused.
        """
        raster = read_raster(
            self.source.resolve(href),
            declared_band_order=MODEL_BANDS,
            declared_scale=BackscatterScale.DECIBEL,
        )
        return reproject_to_area_safe_crs(raster)

    def _load_permanent_water(self, href: str, target: Raster) -> npt.NDArray[np.bool_]:
        """Read the JRC layer onto the analysis grid, nearest-neighbour.

        Nearest because it is a class mask. Interpolating between "water" and "not
        water" invents a value nobody recorded, and here it would invent permanent
        water to subtract.
        """
        from rasterio.enums import Resampling
        from rasterio.warp import reproject

        path = self.source.resolve(href)
        with rasterio.open(path) as source:
            destination = np.zeros((target.spec.height, target.spec.width), dtype=np.uint8)
            reproject(
                source=rasterio.band(source, 1),
                destination=destination,
                src_transform=source.transform,
                src_crs=source.crs,
                dst_transform=target.transform,
                dst_crs=target.spec.crs,
                resampling=Resampling.nearest,
            )
        permanent: npt.NDArray[np.bool_] = destination == 1
        return permanent

    # -- inference ----------------------------------------------------------- #

    def _predict(
        self, model, normalisation, raster: Raster, permanent_water=None
    ) -> npt.NDArray[np.bool_]:
        """Delegates to ml.pipeline.learned so the service and the evaluation
        report cannot drift apart. They did once: the report scored the model on
        the native grid and the baseline on the reprojected one, and only a shape
        mismatch stopped it reporting a wrong comparison.

        The permanent-water layer is passed in rather than re-read. The same array
        already feeds the postprocessing subtraction, and reading it twice is how
        the model ends up conditioned on one grid while the measurement is
        corrected on another. A three-channel model uses it as a prior; a
        two-channel one ignores it, and neither the service nor this method has to
        know which -- ml.pipeline.learned reads the channel count off the
        checkpoint."""
        return predict_water_mask(model, normalisation, raster, permanent_water)

    # -- outcomes ------------------------------------------------------------ #

    def _degraded(
        self,
        raster: Raster,
        *,
        scene: SceneRef,
        trace_id: str,
        permanent_water,
        min_mapping_unit_ha: float,
        reason: str,
        degraded_from: str | None,
    ) -> MissionOutcome:
        """Run the baseline and label the answer as degraded."""
        outcome = detect_water_single_date(
            raster,
            scenes=[scene],
            code_version=self.code_version,
            permanent_water=permanent_water,
            min_mapping_unit_ha=min_mapping_unit_ha,
            trace_id=trace_id,
        )
        if outcome.outcome != "analysed":
            return outcome

        return outcome.model_copy(
            update={
                "degraded_from": degraded_from or BASELINE_METHOD,
                "caveats": outcome.caveats + (f"degraded: {reason}",),
            }
        )

    def _measure(
        self,
        mask: npt.NDArray[np.bool_],
        *,
        raster: Raster,
        scene: SceneRef,
        trace_id: str,
        permanent_water,
        min_mapping_unit_ha: float,
        produced_by: str,
        caveats: tuple[str, ...],
        degraded_from: str | None,
    ) -> MissionOutcome:
        """Postprocess a model mask and turn it into a measured Analysis.

        Same postprocessing the baseline gets. A model output is not exempt from
        speckle removal or permanent-water subtraction — a lake is a lake whichever
        method found it.
        """
        try:
            per_pixel = pixel_area_m2(raster.spec.pixel_size_m, raster.spec.crs)
            cleaned = postprocess_water_mask(
                mask,
                pixel_area_m2=per_pixel,
                permanent_water=permanent_water,
                min_mapping_unit_ha=min_mapping_unit_ha,
            )
        except ValueError as error:
            return self._abstain(
                AbstentionReason.INPUT_FAILED_PREFLIGHT, str(error), scene, trace_id
            )

        measurement = area_hectares(
            cleaned.mask,
            pixel_size_m=raster.spec.pixel_size_m,
            crs=raster.spec.crs,
            derived_from=(scene,),
            code_version=self.code_version,
        )

        return Analysis(
            outcome="analysed",
            measurements=(measurement,),
            geometry_ref=None,
            raster_refs=(),
            # NOT_CALIBRATED, still. The model's sigmoid output is a normalised
            # score, not a probability, and CALIBRATED_PROBABILITY requires a
            # calibration report that does not exist yet (P3-11, D5). Presenting a
            # softmax as a probability is the same class of defect as a fabricated
            # hectare figure.
            confidence=Confidence.not_calibrated(
                caveats=("model output is uncalibrated; see P3-11",)
            ),
            scenes=(scene,),
            degraded_from=degraded_from,
            caveats=(f"produced by {produced_by}",) + caveats + cleaned.caveats,
            trace_id=trace_id,
        )

    @staticmethod
    def _model_caveats(card) -> tuple[str, ...]:
        """Ship the model's held-out score with every answer it produces.

        A caller reading a hectare figure should not have to go and look up how
        good the method is. If the number is worth reporting, so is its accuracy.
        """
        caveats = []
        if card.validation_iou is not None:
            regions = ", ".join(card.validation_regions) or "unspecified regions"
            caveats.append(
                f"held-out IoU {card.validation_iou:.3f} on {regions}, " f"never seen in training"
            )
        if card.baseline_iou is not None:
            caveats.append(
                f"deterministic baseline scores {card.baseline_iou:.3f} on the " "same split"
            )
        return tuple(caveats)

    @staticmethod
    def _abstain(
        reason: AbstentionReason, explanation: str, scene: SceneRef, trace_id: str
    ) -> Abstention:
        return Abstention(
            outcome="abstained",
            reason=reason,
            explanation=explanation,
            nearest_usable=None,
            scenes_seen=(scene,),
            trace_id=trace_id,
        )


__all__ = ["AnalysisService", "ThresholdError", "water_mask_single_date"]
