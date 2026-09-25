import logging
from fastapi import APIRouter, Header, Depends, HTTPException
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel

# Import canonical models and adapters
from packages.contracts import Observation
from packages.contracts.ml import AssetRef
from services.eo_data.search import search_service
from services.eo_data.errors import ErrorResponse
from packages.geo.validation import validate_geojson_geometry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


class SearchRequest(BaseModel):
    polygon: Dict[str, Any]
    start_date: datetime
    end_date: datetime
    cloud_cover: float = 100.0
    provider: str = "bhoonidhi"


class ResolveRequest(BaseModel):
    item_id: str
    asset_key: str
    provider: str = "bhoonidhi"


def verify_auth_context(organization_id: Optional[str] = Header(None)) -> str:
    """Extracts organization_id from verified auth context (Headers)."""
    if not organization_id:
        raise HTTPException(status_code=401, detail="Missing auth context (organization_id)")
    return organization_id


@router.post("/observations/search", response_model=List[Observation])
def search_observations_api(
    req: SearchRequest,
    trace_id: Optional[str] = Header(None),
    mission_id: Optional[str] = Header(None),
    run_id: Optional[str] = Header(None),
    org_id: str = Depends(verify_auth_context),
):
    """
    P4-07: Spatial/temporal observation search endpoint.
    """
    context = {
        "trace_id": trace_id,
        "mission_id": mission_id,
        "run_id": run_id,
        "organization_id": org_id,
    }

    # Audit log
    logger.info(f"AUDIT: org={org_id} action=search trace_id={trace_id}")

    try:
        req.polygon = validate_geojson_geometry(req.polygon)
        results = search_service.search_observations(
            req.polygon,
            req.start_date,
            req.end_date,
            context,
            cloud_cover=req.cloud_cover,
            provider_name=req.provider,
        )
        return results
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        err = ErrorResponse(
            code="SEARCH_FAILED",
            message=str(e),
            details=[repr(e)],
            retryable=True,
            trace_id=trace_id or "unknown",
            mission_id=mission_id,
            organization_id=org_id,
        )
        raise HTTPException(status_code=500, detail=err.model_dump())


@router.post("/monitoring/latest-cloud-free", response_model=Optional[Observation])
def get_latest_cloud_free_api(
    req: SearchRequest,
    trace_id: Optional[str] = Header(None),
    mission_id: Optional[str] = Header(None),
    run_id: Optional[str] = Header(None),
    org_id: str = Depends(verify_auth_context),
):
    """
    P4-18: Identifies the best continuous monitoring observation.
    """
    context = {
        "trace_id": trace_id,
        "mission_id": mission_id,
        "run_id": run_id,
        "organization_id": org_id,
    }
    logger.info(f"AUDIT: org={org_id} action=monitoring_latest_cloud_free trace_id={trace_id}")
    try:
        req.polygon = validate_geojson_geometry(req.polygon)
        return search_service.get_latest_cloud_free_observation(
            req.polygon, context, provider_name=req.provider
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assets/resolve", response_model=AssetRef)
def resolve_asset_api(
    req: ResolveRequest,
    trace_id: Optional[str] = Header(None),
    org_id: str = Depends(verify_auth_context),
):
    """
    P4-08: Asset resolver endpoint.
    Resolves an abstract asset to a physical URI (e.g. downloads and stages to S3).
    """
    context = {"trace_id": trace_id, "organization_id": org_id}
    logger.info(
        f"AUDIT: org={org_id} action=resolve_asset item={req.item_id} asset={req.asset_key}"
    )
    try:
        if req.provider == "bhoonidhi":
            from packages.providers.bhoonidhi import BhoonidhiAdapter

            adapter = BhoonidhiAdapter()
            s3_uri = adapter.get_asset(req.item_id, req.asset_key, context)

            # P4-08: Complete AssetRef metadata
            from packages.contracts.ml import AssetRef
            from packages.providers.config import config

            titiler_base = getattr(config, "titiler_url", "http://localhost:8081").rstrip("/")
            titiler_url = f"{titiler_base}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}?url={s3_uri}"

            return AssetRef(
                s3_uri=s3_uri, titiler_url=titiler_url, item_id=req.item_id, asset_key=req.asset_key
            )
        else:
            raise ValueError(f"Provider {req.provider} resolution not implemented.")
    except Exception as e:
        err = ErrorResponse(
            code="RESOLVE_FAILED",
            message=str(e),
            details=[],
            retryable=False,
            trace_id=trace_id or "unknown",
            organization_id=org_id,
        )
        raise HTTPException(status_code=500, detail=err.model_dump())
