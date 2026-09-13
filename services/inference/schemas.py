"""Request shapes for the inference API.

The *response* shapes are not defined here. They are `Analysis | Abstention` from
`ml.contracts.outcome`, unchanged — the same objects the pipeline produces
internally. Defining a separate API response model would create a second place
where a number can lose its provenance in translation, and provenance surviving
the trip to the caller is the whole point of the contract layer (ADR-0007 D2).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ml.contracts.scene import SceneRef


class AnalysisRequest(BaseModel):
    """Ask for one scene to be analysed for surface water.

    ``extra="forbid"`` so a caller that misspells a field is told, rather than
    silently getting default behaviour. P2 and P5 both generate clients against
    this; a typo that validates is a bug discovered at demo time.
    """

    model_config = ConfigDict(extra="forbid")

    scene: SceneRef = Field(
        description="Provenance for the scene being analysed. Travels through to "
        "every Measurement's derived_from, so the answer can name its input."
    )
    scene_href: str = Field(
        min_length=1,
        description="Where the raster is. Checked against the provider allowlist "
        "before anything dereferences it.",
    )
    permanent_water_href: str | None = Field(
        default=None,
        description="Optional mask of water present before the event. Strongly "
        "recommended: without it, rivers and lakes are counted as flooding, which "
        "is the most damaging false positive this service can emit.",
    )
    model: str | None = Field(
        default=None,
        description="Model to use. Omit for the best model that beats the "
        "deterministic baseline on held-out regions, or 'baseline' to force the "
        "deterministic path.",
    )
    min_mapping_unit_ha: float = Field(
        default=0.5,
        ge=0.0,
        description="Smallest patch reported as a distinct flood, in hectares. "
        "Expressed as area rather than pixels because pixel size varies by "
        "provider.",
    )


class ModelSummary(BaseModel):
    """One registered model and the evidence for using it."""

    name: str
    version: str
    parameters: int
    validation_iou: float | None
    validation_f1: float | None
    validation_regions: list[str]
    train_regions: list[str]
    baseline_iou: float | None
    beats_baseline: bool | None = Field(
        description="Whether this model outscored the deterministic baseline on "
        "the same held-out split. null means it was not measured — which is a "
        "different claim from 'it lost', and they must not be collapsed."
    )
    stratified_iou: dict[str, float] = Field(
        default_factory=dict,
        description="IoU by how much water the chip contains. A single mean says "
        "as much about the sample's wet/dry mix as about the method.",
    )


class ModelListResponse(BaseModel):
    models: list[ModelSummary]
    default: str | None = Field(
        description="Selected when a request names no model. null when no "
        "registered model beats the baseline, in which case the deterministic "
        "path is used and the result is labelled as degraded."
    )
