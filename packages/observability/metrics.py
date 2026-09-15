"""
packages/observability/metrics.py — Prometheus metrics for the API gateway (P6-14)

Exposes the metric families the provisioned Grafana dashboard
(satquery-overview.json) queries:

  http_server_requests_seconds{method, path, status}   (Histogram, seconds)
  http_server_requests_total{method, path, status}     (Counter)

Rendered at ``/metrics`` in the Prometheus text exposition format so that the
``satquery-api`` scrape job in prometheus.yml collects them directly.

Uses prometheus_client's explicit CollectorRegistry (not the global default)
so importing this module never leaks state between test processes, and
rendering an exposition payload is a pure function — safe to call from unit
tests without a server.
"""

import time
from typing import Any, Dict, Optional

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.utils import INF
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# ── Metric definitions ────────────────────────────────────────────────────────

REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS = Histogram(
    "http_server_requests_seconds",
    "HTTP request latency in seconds",
    labelnames=("method", "path", "status"),
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
        INF,
    ),
    registry=REGISTRY,
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_server_requests_total",
    "Total count of HTTP requests",
    labelnames=("method", "path", "status"),
    registry=REGISTRY,
)

#: Fallback path label when the ASGI scope has no routable path.
_UNKNOWN_PATH = "UNKNOWN"

#: Path templates are recorded instead of raw URLs — raw request paths would
#: create one Prometheus time series per URL (unbounded label cardinality,
#: a resource-exhaustion vector) whenever an ID appears in the path.
_MAX_TEMPLATE_CACHE = 512
_template_cache: Dict[str, str] = {}


def route_matches(path: str, path_format: str) -> bool:
    """Whether ``path`` matches a Starlette route template.

    Supports ``{param}`` placeholders (non-empty, single segment), which covers
    every route shape in the gateway. Kept dependency-free so the metrics
    module has no import-time coupling to Starlette internals.
    """
    if "{" not in path_format:
        return path == path_format
    path_parts = path.split("/")
    fmt_parts = path_format.split("/")
    if len(path_parts) != len(fmt_parts):
        return False
    for part, fmt in zip(path_parts, fmt_parts):
        if fmt.startswith("{") and fmt.endswith("}"):
            if not part:
                return False
        elif part != fmt:
            return False
    return True


def _path_template(scope: Scope) -> str:
    """Best-effort route template for the request path.

    Prefers the route's ``path_format`` (e.g. ``/api/v1/missions/{mission_id}``)
    so that distinct mission/job IDs do not explode label cardinality.
    """
    raw_path = scope.get("path") or ""
    cached = _template_cache.get(raw_path)
    if cached is not None:
        return cached

    template = raw_path or _UNKNOWN_PATH
    app: Any = scope.get("app")
    routes = getattr(app, "routes", None) or []
    for route in routes:
        path_format = getattr(route, "path_format", None)
        if path_format and route_matches(raw_path, path_format):
            template = path_format
            break

    if len(_template_cache) < _MAX_TEMPLATE_CACHE:
        _template_cache[raw_path] = template
    return template


# ── Exposition ────────────────────────────────────────────────────────────────


def render_metrics() -> bytes:
    """Render the registry in the Prometheus text exposition format."""
    return generate_latest(REGISTRY)


# ── ASGI instrumentation ──────────────────────────────────────────────────────


class MetricsMiddleware:
    """Pure-ASGI middleware: records latency + status for every HTTP request.

    WebSocket scopes are ignored. Unhandled exceptions are attributed to a
    500 series count so failed requests still show up in the error-rate panel.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = _path_template(scope)
        start = time.perf_counter()
        recorded: Dict[str, Optional[str]] = {"status": None}

        def record(status: str) -> None:
            elapsed = time.perf_counter() - start
            HTTP_REQUESTS.labels(method=method, path=path, status=status).observe(elapsed)
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status = str(message["status"])
                recorded["status"] = status
                record(status)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Unhandled exception: the response may never have started, so no
            # sample was recorded yet. Attribute it to a 500.
            if recorded["status"] is None:
                record("500")
            raise
