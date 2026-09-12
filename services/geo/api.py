from fastapi import APIRouter, Header, Depends, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel

try:
    from titiler.core.factory import TilerFactory

    TITILER_AVAILABLE = True
except ImportError:
    TITILER_AVAILABLE = False

from services.geo.implementation import process_geo_job
from services.eo_data.errors import ErrorResponse

router = APIRouter(prefix="/api/v1")


class GeoJobRequest(BaseModel):
    job_payload: Dict[str, Any]


def verify_auth_context(organization_id: Optional[str] = Header(None)) -> str:
    """Extracts organization_id from verified auth context (Headers)."""
    if not organization_id:
        raise HTTPException(status_code=401, detail="Missing auth context (organization_id)")
    return organization_id


# P4-15: TiTiler Integration
if TITILER_AVAILABLE:
    # Mount actual titiler dynamic tile generation
    cog_tiler = TilerFactory()
    router.include_router(cog_tiler.router, prefix="/tiles", tags=["tiles"])
else:

    @router.get("/tiles/{z}/{x}/{y}")
    def fallback_tiles(z: int, x: int, y: int):
        raise HTTPException(
            status_code=501, detail="titiler.core missing from environment. Tiles unavailable."
        )


@router.post("/geo/jobs", status_code=202)
def submit_geo_job_api(
    req: GeoJobRequest,
    idempotency_key: str = Header(...),
    trace_id: Optional[str] = Header(None),
    job_id: Optional[str] = Header(None),
    org_id: str = Depends(verify_auth_context),
):
    """
    P4-16: Async GeoJob worker endpoint.
    Accepts long-running geo requests and delegates to Celery.
    Returns 202 Accepted + job_id.
    """
    import uuid

    actual_job_id = job_id or str(uuid.uuid4())

    context = {"trace_id": trace_id, "job_id": actual_job_id, "organization_id": org_id}

    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        f"AUDIT: org={org_id} action=submit_geo_job job_id={actual_job_id} trace_id={trace_id}"
    )

    try:
        # Dispatch to celery worker
        process_geo_job.delay(actual_job_id, idempotency_key, req.job_payload, context)

        # Engineering Rules: "Long-running EO/ML/report/monitoring work returns 202 + job_id."
        return {"status": "accepted", "job_id": actual_job_id}
    except Exception as e:
        err = ErrorResponse(
            code="JOB_DISPATCH_FAILED",
            message=str(e),
            details=[],
            retryable=True,
            trace_id=trace_id or "unknown",
            job_id=actual_job_id,
            organization_id=org_id,
        )
        raise HTTPException(status_code=500, detail=err.model_dump())
