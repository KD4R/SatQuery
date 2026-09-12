"""
services/agent/app/api/implementation.py — Agent FastAPI application (P2-01).

Registers:
  - Idempotency middleware
  - Structured logging & OpenTelemetry instrumentation
  - Canonical ErrorResponse exception handlers
  - Routers:
      /api/v1/health
      /api/v1/agent/plan
      /api/v1/agent/execute
      /api/v1/agent/sensor-decision
      /api/v1/agent/confidence
"""

from typing import Optional
from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from packages.contracts.errors import ErrorDetail, ErrorResponse
from packages.observability import setup_logging, setup_telemetry
from packages.shared.middleware import IdempotencyMiddleware
from security.exceptions import GeometryValidationError, PromptInjectionError
from services.agent.app.api.routers.confidence import router as confidence_router
from services.agent.app.api.routers.execute import router as execute_router
from services.agent.app.api.routers.plan import router as plan_router
from services.agent.app.api.routers.sensor_decision import router as sensor_decision_router

setup_logging("agent")

app = FastAPI(
    title="SatQuery Agent Service",
    description="AI Agent & LangGraph Orchestrator for SatQuery AI",
    version="1.0.0",
)

app.add_middleware(IdempotencyMiddleware)

# ── Canonical Error Handlers ───────────────────────────────────────────────────


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")
    details = [
        ErrorDetail(
            message=err.get("msg", "Validation error"),
            code=err.get("type", "VALIDATION_ERROR"),
        )
        for err in exc.errors()
    ]
    err_body = ErrorResponse(
        code="VALIDATION_ERROR",
        message="Request validation failed against schema",
        details=details,
        retryable=False,
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=err_body.model_dump()
    )


@app.exception_handler(PromptInjectionError)
async def prompt_injection_exception_handler(
    request: Request, exc: PromptInjectionError
) -> JSONResponse:
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")
    err_body = ErrorResponse(
        code=exc.code,
        message=exc.message,
        details=[ErrorDetail(message=exc.message, code=exc.code)],
        retryable=False,
        trace_id=trace_id,
    )
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=err_body.model_dump())


@app.exception_handler(GeometryValidationError)
async def geometry_validation_exception_handler(
    request: Request, exc: GeometryValidationError
) -> JSONResponse:
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")
    err_body = ErrorResponse(
        code=exc.code,
        message=exc.message,
        details=[ErrorDetail(message=exc.message, code=exc.code)],
        retryable=False,
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=err_body.model_dump()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "HTTP_ERROR")
        msg = exc.detail.get("message", "An error occurred")
        retryable = exc.detail.get("retryable", False)
        t_id = exc.detail.get("trace_id", trace_id)
    else:
        code = "HTTP_ERROR"
        msg = str(exc.detail)
        retryable = False
        t_id = trace_id

    err_body = ErrorResponse(
        code=code,
        message=msg,
        details=[],
        retryable=retryable,
        trace_id=t_id,
    )
    return JSONResponse(status_code=exc.status_code, content=err_body.model_dump())


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(plan_router)
app.include_router(execute_router)
app.include_router(sensor_decision_router)
app.include_router(confidence_router)

_health_router = APIRouter(prefix="/api/v1")


class HealthStatus(BaseModel):
    status: str
    service: str


@_health_router.get("/health", response_model=HealthStatus)
async def health_check():
    return HealthStatus(status="ok", service="agent")


app.include_router(_health_router)
setup_telemetry(app, "agent")
