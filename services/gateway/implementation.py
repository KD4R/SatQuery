"""
services/gateway/implementation.py — Gateway/BFF FastAPI application (P1-05, P1-08).

Registers:
  - CORS middleware (configurable origins from CORS_ALLOW_ORIGINS env var)
  - Rate limiting middleware (sliding window)
  - Health router
  - WebSocket mission status stream
"""

import os

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from packages.observability import setup_logging, setup_telemetry
from packages.observability.metrics import MetricsMiddleware, render_metrics
from packages.shared.middleware import IdempotencyMiddleware
from services.gateway.config import get_gateway_settings
from services.gateway.middleware.rate_limit import RateLimitMiddleware
from services.gateway.middleware.security_headers import SecurityHeadersMiddleware
from services.gateway.routers.missions_ws import router as ws_router
from services.gateway.routers.proxy import router as proxy_router

setup_logging("gateway")

app = FastAPI(
    title="SatQuery Gateway",
    description="API Gateway and BFF for SatQuery AI",
    # Middleware order (last added = outermost): metrics outermost so OPTIONS
    # preflights and CORS-rejected requests are counted too.
    version="1.0.0",
)

app.add_middleware(IdempotencyMiddleware)


@app.exception_handler(StarletteHTTPException)
async def canonical_error_response(request: Request, exc: StarletteHTTPException):
    """Emit the frozen ErrorResponse shape (P1-02, P1-10) for gateway-raised errors.

    Routers raise ``HTTPException(detail={"code", "message", "retryable"})``, which
    FastAPI would serialise as ``{"detail": {...}}``. The contract, the browser
    client and the integration tests all expect the flat envelope
    ``{code, message, details, retryable, trace_id}``, so a circuit-open 503 or a
    mapped upstream error must not arrive wrapped. Anything that is not already
    shaped like an envelope keeps FastAPI's default rendering.
    """
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        body = {
            "code": detail["code"],
            "message": detail["message"],
            "details": detail.get("details", []),
            "retryable": bool(detail.get("retryable", False)),
            "trace_id": detail.get("trace_id") or request.headers.get("X-Trace-Id"),
        }
        return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)
    return await http_exception_handler(request, exc)


# ── Middleware ─────────────────────────────────────────────────────────────────
settings = get_gateway_settings()

# CORS — only allow explicitly configured origins (deny all by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
    expose_headers=["X-Trace-Id", "X-Request-Id"],
)

# Rate limiter
app.add_middleware(
    RateLimitMiddleware,
    requests=settings.rate_limit_requests,
    window_s=settings.rate_limit_window_s,
    # Only trust X-Forwarded-For when explicitly deployed behind a proxy that
    # overwrites it — client-supplied values would defeat per-IP limiting.
    trust_proxy_headers=os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true",
)

# Security response headers (A05) — added after the rate limiter so it sits
# inside it and still decorates 429 responses.
app.add_middleware(SecurityHeadersMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.add_middleware(MetricsMiddleware)

app.include_router(ws_router)
app.include_router(proxy_router)

_api_router = APIRouter(prefix="/api/v1")


class HealthStatus(BaseModel):
    status: str
    service: str


@_api_router.get("/health", response_model=HealthStatus)
@_api_router.get("/ready", response_model=HealthStatus)
async def health_check():
    return HealthStatus(status="ok", service="gateway")


@app.get("/health", response_model=HealthStatus, include_in_schema=False)
@app.get("/ready", response_model=HealthStatus, include_in_schema=False)
async def root_health_check():
    return HealthStatus(status="ok", service="gateway")


# ── Prometheus exposition (P6-14) ────────────────────────────────────────────
# Scraped by the `satquery-api` job in prometheus.yml (metrics_path: /metrics).
# Text exposition format, no auth: metrics expose only aggregate counters, and
# the port is not published outside the compose network in production.
@app.get(
    "/metrics",
    include_in_schema=False,
    responses={200: {"content": {"text/plain": {}}}},
)
async def prometheus_metrics() -> Response:
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")


app.include_router(_api_router)
setup_telemetry(app, "gateway")
