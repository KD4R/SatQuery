"""services/inference/routers/inference.py — the P3 inference API (P3-01).

Routes:
  POST /api/v1/inference/analyses   Analyse one scene   (ANALYST+)
  GET  /api/v1/inference/models     List models         (VIEWER+)

ANALYST rather than OPERATOR for running an analysis, matching the role model in
packages/auth/models.py: ANALYST "can create missions and run analyses", while
OPERATOR is for managing AOIs and approving jobs. Requiring OPERATOR would lock
out exactly the people the service is for.

On the path prefix — OPEN-1 is still open
------------------------------------------
The P3 engineering spec says `/api/v1/inference/*`; the Master PRD §16 says
`/api/v1/analysis`. Nobody has ruled, and P5 generates its TypeScript client from
this OpenAPI, so a wrong guess is discovered at integration rather than now.

`/api/v1/inference` is used because it matches how every other service in this
repository is laid out — mission owns `/api/v1/missions`, so inference owns
`/api/v1/inference`. The prefix is a single constant below: if P1 rules the other
way it is a one-line change, which is why building against a guess beat waiting
for the answer.

Synchronous, for now
--------------------
Analysis runs inline and the response carries the result. Inference on one chip is
seconds on CPU, so this is honest for the current scale; P3-10 adds the async
worker and a job handle for larger AOIs. Mission's job router (P1-07) already
anticipates that hand-off.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from packages.contracts import MissionOutcome
from packages.auth import require_role
from packages.auth.models import AuthContext, Role
from services.inference.artifacts import ArtifactNotFound, ArtifactSink
from services.inference.dependencies import (
    get_analysis_service,
    get_artifact_sink,
    get_registry,
)
from services.inference.registry import ModelRegistry
from services.inference.schemas import (
    AnalysisRequest,
    ModelListResponse,
    ModelSummary,
)
from services.inference.service import AnalysisService

logger = logging.getLogger(__name__)

#: Change here if OPEN-1 resolves the other way.
PREFIX = "/api/v1/inference"

router = APIRouter(prefix=PREFIX, tags=["inference"])


@router.post(
    "/analyses",
    response_model=MissionOutcome,
    summary="Analyse one scene for surface water",
    response_description=(
        "An Analysis carrying measurements with full provenance, or an Abstention "
        "carrying a machine-readable reason. There is no third outcome and no "
        "empty result with zeroed values."
    ),
)
async def create_analysis(
    request: AnalysisRequest,
    context: AuthContext = Depends(require_role(Role.ANALYST)),
    service: AnalysisService = Depends(get_analysis_service),
) -> MissionOutcome:
    """Run one analysis.

    Returns 200 for both outcomes. An abstention is a successful answer to the
    question "can you measure this?" — the answer is no, and the reason is
    machine-readable. Returning 4xx or 5xx would make the caller treat a correct,
    considered refusal as a transport failure and retry it.
    """
    trace_id = str(uuid.uuid4())
    outcome = service.analyse(
        scene=request.scene,
        scene_href=request.scene_href,
        permanent_water_href=request.permanent_water_href,
        model_name=request.model,
        min_mapping_unit_ha=request.min_mapping_unit_ha,
        trace_id=trace_id,
    )

    logger.info(
        "analysis %s outcome=%s tenant=%s",
        trace_id,
        outcome.outcome,
        getattr(context, "tenant_id", None),
    )
    return outcome


@router.get(
    "/models",
    response_model=ModelListResponse,
    summary="List registered models and their held-out scores",
)
async def list_models(
    context: AuthContext = Depends(require_role(Role.VIEWER)),
    registry: ModelRegistry = Depends(get_registry),
) -> ModelListResponse:
    """What models exist, what they scored, and which one runs by default.

    An empty list is a valid, meaningful answer: it means every analysis will use
    the deterministic baseline, and each result will say so via `degraded_from`.
    """
    return ModelListResponse(
        models=[ModelSummary(**card.to_dict()) for card in registry.cards()],
        default=registry.default(),
    )


@router.get(
    "/analyses/{trace_id}/extent",
    summary="The water extent an analysis measured, as GeoJSON (EPSG:4326)",
    responses={
        200: {"content": {"application/geo+json": {}}},
        404: {"description": "No stored extent for this analysis"},
        503: {"description": "No artifact store is configured"},
    },
)
async def get_extent(
    trace_id: uuid.UUID,
    context: AuthContext = Depends(require_role(Role.VIEWER)),
    sink: ArtifactSink | None = Depends(get_artifact_sink),
) -> Response:
    """The polygons behind an analysis's hectare figure.

    Exists so the browser can draw them. ``Analysis.geometry_ref`` is an object-
    storage key, and the browser may only talk to the gateway -- so the extent is
    served through the service that wrote it, behind the same auth, instead of by
    handing out bucket URLs.

    ``trace_id`` is typed as a UUID, which is what the analysis endpoint issues.
    FastAPI rejects anything else with a 422 before this runs, so no caller-supplied
    string ever reaches a storage key.
    """
    if sink is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "NO_ARTIFACT_STORE",
                "message": "This inference service is not configured to keep outputs.",
                "retryable": False,
            },
        )
    try:
        body = sink.get(f"analyses/{trace_id}/water_extent.geojson")
    except ArtifactNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "EXTENT_NOT_FOUND",
                "message": "No stored extent for this analysis.",
                "retryable": False,
            },
        )
    return Response(content=body, media_type="application/geo+json")
