"""
services/gateway/implementation.py — Gateway/BFF FastAPI application (P1-05, P1-08).

Registers:
  - CORS middleware (configurable origins from CORS_ALLOW_ORIGINS env var)
  - Rate limiting middleware (sliding window)
  - Health router
  - WebSocket mission status stream
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from packages.observability import setup_logging, setup_telemetry
from services.gateway.config import get_gateway_settings
from services.gateway.middleware.rate_limit import RateLimitMiddleware
from services.gateway.routers.missions_ws import router as ws_router

setup_logging("gateway")

app = FastAPI(
    title="SatQuery Gateway",
    description="API Gateway / BFF for SatQuery AI",
    version="1.0.0",
)

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
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(ws_router)

_api_router = APIRouter(prefix="/api/v1")


class HealthStatus(BaseModel):
    status: str
    service: str


@_api_router.get("/health", response_model=HealthStatus)
async def health_check():
    return HealthStatus(status="ok", service="gateway")


app.include_router(_api_router)
setup_telemetry(app, "gateway")
