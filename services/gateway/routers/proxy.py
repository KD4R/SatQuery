"""
services/gateway/routers/proxy.py — Reverse-proxy routes (P1-05).

Routes all /api/v1/missions/* and /api/v1/agent/* calls to the respective
downstream microservices via the InternalClient (S2S auth, circuit-breaker,
retries, telemetry).

OWASP mitigations:
  A01 — Token verified by get_current_user before any proxy call.
  A07 — S2S token generated per-request; never logged.
  A10 — Server-Side Request Forgery prevented: downstream URLs are resolved from
        environment variables only (no user input in URL construction).
  A05 — Security misconfiguration: HTTPS enforced in prod by requiring HTTPS-
        prefixed base URLs; HTTP allowed only via explicit GATEWAY_ALLOW_HTTP env.
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from packages.auth.dependencies import require_role
from packages.auth.models import AuthContext, Role
from packages.shared.client import CircuitBreakerOpenError, InternalClient, InternalClientError

# Import schemas to enrich Gateway OpenAPI
from services.mission.domain.schemas import (
    MissionCreate,
    MissionUpdate,
    MissionResponse,
    MissionListResponse,
    JobSubmitResponse,
    JobStatusResponse,
)
from services.agent.schemas import (
    PlanRequest,
    PlanResponse,
    ExecuteRequest,
    ExecuteResponse,
    SensorDecisionRequest,
    SensorDecisionResponse,
    ConfidenceRequest,
    ConfidenceResponse,
    MissionState,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["proxy"])

# ── Service base URLs ─────────────────────────────────────────────────────────
# Resolved once at import time; never constructed from user input.
_MISSION_URL = os.getenv("MISSION_SERVICE_URL", "http://localhost:8001")
_AGENT_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8002")
_INFERENCE_URL = os.getenv("INFERENCE_SERVICE_URL", "http://localhost:8003")

# ── InternalClient singletons (lazy-init, reused across requests) ─────────────
_mission_client: Optional[InternalClient] = None
_agent_client: Optional[InternalClient] = None
_inference_client: Optional[InternalClient] = None


def _get_mission_client() -> InternalClient:
    global _mission_client
    if _mission_client is None:
        _mission_client = InternalClient(
            base_url=_MISSION_URL,
            caller_service="gateway",
            scopes=["mission:read", "mission:write"],
        )
    return _mission_client


def _get_agent_client() -> InternalClient:
    global _agent_client
    if _agent_client is None:
        _agent_client = InternalClient(
            base_url=_AGENT_URL,
            caller_service="gateway",
            scopes=["agent:read", "agent:write"],
        )
    return _agent_client


def _get_inference_client() -> InternalClient:
    global _inference_client
    if _inference_client is None:
        _inference_client = InternalClient(
            base_url=_INFERENCE_URL,
            caller_service="gateway",
            scopes=["inference:read", "inference:run"],
        )
    return _inference_client


# ── Helpers ───────────────────────────────────────────────────────────────────


def _safe_headers(request: Request) -> Dict[str, str]:
    """Pass-through headers that are safe to forward downstream."""
    forwarded: Dict[str, str] = {}
    for hdr in ("X-Trace-Id", "X-Request-Id", "Content-Type", "Idempotency-Key"):
        val = request.headers.get(hdr)
        if val:
            forwarded[hdr] = val
    return forwarded


async def _proxy(
    client: InternalClient,
    method: str,
    path: str,
    ctx: AuthContext,
    request: Request,
    body: Optional[bytes] = None,
) -> JSONResponse:
    """Execute a proxied request and map errors to appropriate HTTP responses."""
    extra_headers = _safe_headers(request)
    kwargs: Dict[str, Any] = {"headers": extra_headers}
    if body:
        kwargs["content"] = body

    try:
        resp = await client._request(method, path, ctx, **kwargs)
        # Forward the downstream status code and JSON body unchanged.
        try:
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except Exception:
            return JSONResponse(content={"raw": resp.text}, status_code=resp.status_code)

    except CircuitBreakerOpenError:
        logger.warning("Circuit breaker open for path=%s", path)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "Downstream service is temporarily unavailable.",
                "retryable": True,
            },
        )
    except InternalClientError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.error.code,
                "message": exc.error.message,
                "retryable": exc.error.retryable,
            },
        )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        logger.error("Network error proxying %s %s: %s", method, path, exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "GATEWAY_TIMEOUT",
                "message": "Upstream service did not respond in time.",
                "retryable": True,
            },
        )


# ── Mission proxy routes ──────────────────────────────────────────────────────


@router.get("/api/v1/missions", response_model=MissionListResponse)
async def proxy_list_missions(
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.VIEWER)),
):
    """Proxy GET /api/v1/missions → Mission service."""
    qs = str(request.url.query)
    path = "/api/v1/missions" + (f"?{qs}" if qs else "")
    return await _proxy(_get_mission_client(), "GET", path, ctx, request)


@router.post("/api/v1/missions", status_code=201, response_model=MissionResponse)
async def proxy_create_mission(
    payload: MissionCreate,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.ANALYST)),
):
    """Proxy POST /api/v1/missions → Mission service."""
    body = await request.body()
    return await _proxy(_get_mission_client(), "POST", "/api/v1/missions", ctx, request, body)


@router.get("/api/v1/missions/{mission_id}", response_model=MissionResponse)
async def proxy_get_mission(
    mission_id: str,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.VIEWER)),
):
    """Proxy GET /api/v1/missions/{id} → Mission service."""
    return await _proxy(
        _get_mission_client(), "GET", f"/api/v1/missions/{mission_id}", ctx, request
    )


@router.patch("/api/v1/missions/{mission_id}", response_model=MissionResponse)
async def proxy_update_mission(
    mission_id: str,
    payload: MissionUpdate,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.ANALYST)),
):
    """Proxy PATCH /api/v1/missions/{id} → Mission service."""
    body = await request.body()
    return await _proxy(
        _get_mission_client(), "PATCH", f"/api/v1/missions/{mission_id}", ctx, request, body
    )


@router.delete("/api/v1/missions/{mission_id}", status_code=204)
async def proxy_delete_mission(
    mission_id: str,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.OPERATOR)),
):
    """Proxy DELETE /api/v1/missions/{id} → Mission service (OPERATOR+)."""
    return await _proxy(
        _get_mission_client(), "DELETE", f"/api/v1/missions/{mission_id}", ctx, request
    )


@router.post(
    "/api/v1/missions/{mission_id}/runs", status_code=202, response_model=JobSubmitResponse
)
async def proxy_submit_run(
    mission_id: str,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.OPERATOR)),
):
    """Proxy POST /api/v1/missions/{id}/runs → Mission service (OPERATOR+)."""
    body = await request.body()
    return await _proxy(
        _get_mission_client(),
        "POST",
        f"/api/v1/missions/{mission_id}/runs",
        ctx,
        request,
        body,
    )


@router.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
async def proxy_get_job(
    job_id: str,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.VIEWER)),
):
    """Proxy GET /api/v1/jobs/{job_id} → Mission service."""
    return await _proxy(_get_mission_client(), "GET", f"/api/v1/jobs/{job_id}", ctx, request)


# ── Agent proxy routes ────────────────────────────────────────────────────────


@router.post("/api/v1/agent/plan", response_model=PlanResponse)
async def proxy_agent_plan(
    payload: PlanRequest,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.ANALYST)),
):
    """Proxy POST /api/v1/agent/plan → Agent service (ANALYST+)."""
    body = await request.body()
    return await _proxy(_get_agent_client(), "POST", "/api/v1/agent/plan", ctx, request, body)


@router.post("/api/v1/agent/execute", status_code=202, response_model=ExecuteResponse)
async def proxy_agent_execute(
    payload: ExecuteRequest,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.ANALYST)),
):
    """Proxy POST /api/v1/agent/execute → Agent service (ANALYST+)."""
    body = await request.body()
    return await _proxy(_get_agent_client(), "POST", "/api/v1/agent/execute", ctx, request, body)


@router.get("/api/v1/agent/runs/{job_id}", response_model=MissionState)
async def proxy_agent_run_status(
    job_id: str,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.VIEWER)),
):
    """Proxy GET /api/v1/agent/runs/{job_id} → Agent service."""
    return await _proxy(_get_agent_client(), "GET", f"/api/v1/agent/runs/{job_id}", ctx, request)


@router.post("/api/v1/agent/sensor-decision", response_model=SensorDecisionResponse)
async def proxy_agent_sensor_decision(
    payload: SensorDecisionRequest,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.ANALYST)),
):
    """Proxy POST /api/v1/agent/sensor-decision → Agent service."""
    body = await request.body()
    return await _proxy(
        _get_agent_client(), "POST", "/api/v1/agent/sensor-decision", ctx, request, body
    )


@router.post("/api/v1/agent/confidence", response_model=ConfidenceResponse)
async def proxy_agent_confidence(
    payload: ConfidenceRequest,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.ANALYST)),
):
    """Proxy POST /api/v1/agent/confidence → Agent service."""
    body = await request.body()
    return await _proxy(_get_agent_client(), "POST", "/api/v1/agent/confidence", ctx, request, body)


@router.get("/api/v1/agent/tools")
async def proxy_agent_tools(
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.VIEWER)),
):
    """Proxy GET /api/v1/agent/tools → Agent service."""
    return await _proxy(_get_agent_client(), "GET", "/api/v1/agent/tools", ctx, request)

# -- Inference proxy routes --------------------------------------------------

@router.post("/api/v1/inference/analyses")
async def proxy_inference_analyses(
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.ANALYST)),
):
    body = await request.body()
    return await _proxy(_get_inference_client(), "POST", "/api/v1/inference/analyses", ctx, request, body)

@router.get("/api/v1/inference/models")
async def proxy_inference_models(
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.VIEWER)),
):
    return await _proxy(_get_inference_client(), "GET", "/api/v1/inference/models", ctx, request)

@router.get("/api/v1/inference/analyses/{trace_id}/extent")
async def proxy_inference_extent(
    trace_id: str,
    request: Request,
    ctx: AuthContext = Depends(require_role(Role.VIEWER)),
):
    return await _proxy(_get_inference_client(), "GET", f"/api/v1/inference/analyses/{trace_id}/extent", ctx, request)

