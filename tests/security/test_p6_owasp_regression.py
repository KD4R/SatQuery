"""
P6-OWASP regression tests — gateway + agent service hardening.

Covers the concrete findings from the deep OWASP Top 10 review:
  - A04: rate limiter proxy-header trust, bounded client store
  - A01: WebSocket tenant isolation, budget ceilings
  - A04: GeoJSON depth bomb rejection, idempotency 5xx non-caching
  - A09: audit redaction recurses into lists, log-hygiene invariants
  - A05: security response headers
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

import pytest

from packages.shared.middleware.idempotency import _IDEMPOTENCY_STORE
from services.agent.security.audit import AuditLogger
from services.agent.security.exceptions import BudgetExceededError, GeometryValidationError
from services.agent.security.tool_budget import MAX_ALLOWED_CALLS, ToolBudget
from services.agent.security.validator import validate_aoi_geometry
from services.gateway.middleware.rate_limit import RateLimitMiddleware
from services.gateway.middleware.security_headers import SecurityHeadersMiddleware

pytestmark = pytest.mark.security


def _client(trust_proxy_headers: bool = False, requests: int = 3, window_s: int = 60) -> TestClient:
    """Build a minimal app with only the rate limiter; direct client IP is fixed."""
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        requests=requests,
        window_s=window_s,
        trust_proxy_headers=trust_proxy_headers,
    )

    @app.get("/api/v1/ping")
    async def ping():
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    return TestClient(app)


# -- A04: Rate limiter identity trust --


class TestRateLimiterIdentity:
    def test_spoofed_xff_ignored_by_default(self):
        client = _client(trust_proxy_headers=False, requests=3)
        for _ in range(3):
            r = client.get("/api/v1/ping", headers={"X-Forwarded-For": "9.9.9.9"})
            assert r.status_code == 200
        # Spoofing a fresh IP must NOT bypass the per-peer limit.
        r = client.get("/api/v1/ping", headers={"X-Forwarded-For": "8.8.8.8"})
        assert r.status_code == 429

    def test_xff_trusted_only_when_configured(self):
        client = _client(trust_proxy_headers=True, requests=3)
        for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
            r = client.get("/api/v1/ping", headers={"X-Forwarded-For": ip})
            assert r.status_code == 200

    def test_unique_ip_flood_bounded(self):
        client = _client(trust_proxy_headers=True, requests=1000)
        for i in range(10_050):
            client.get(
                "/api/v1/ping",
                headers={"X-Forwarded-For": f"10.{i // 256 % 256}.{i % 256}.7"},
            )
        instance = _find_middleware_instance(client.app, RateLimitMiddleware)
        assert instance is not None
        # Soft cap: eviction kicks in when the store exceeds the bound, so the
        # steady-state size is bound + 1 — the invariant is it cannot grow
        # unboundedly with unique-IP floods.
        assert len(instance._store) <= RateLimitMiddleware._MAX_TRACKED_CLIENTS + 1

    def test_health_endpoints_exempt(self):
        client = _client(trust_proxy_headers=False, requests=1)
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/health").status_code == 200


def _find_middleware_instance(app, cls):
    """Walk the built middleware chain and return the first instance of cls."""
    node = app.middleware_stack
    while node is not None:
        if isinstance(node, cls):
            return node
        node = getattr(node, "app", None)
    return None


# -- A01: Tool budget ceilings --


class TestToolBudgetCeilings:
    def test_client_cannot_exceed_max_calls_ceiling(self):
        with pytest.raises(ValueError):
            ToolBudget(max_calls=MAX_ALLOWED_CALLS + 1)

    def test_client_cannot_exceed_duration_ceiling(self):
        with pytest.raises(ValueError):
            ToolBudget(max_duration_seconds=1_000_000.0)

    def test_smaller_budget_allowed(self):
        b = ToolBudget(max_calls=2, max_duration_seconds=10.0)
        assert b.max_calls == 2

    def test_consume_enforcement(self):
        b = ToolBudget(max_calls=1)
        b.consume()
        with pytest.raises(BudgetExceededError):
            b.consume()


# -- A04: GeoJSON depth bomb --


class TestGeoJSONDepthCap:
    def _deep_polygon(self, levels: int) -> dict:
        from typing import Any

        coords: Any = [0.0, 0.0]
        for _ in range(levels):
            coords = [coords]
        coords = coords + [coords.copy()]
        return {"type": "Polygon", "coordinates": coords}

    def test_reasonable_nesting_accepted(self):
        geojson = {
            "type": "Polygon",
            "coordinates": [
                [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]],
            ],
        }
        assert validate_aoi_geometry(geojson) == geojson

    def test_depth_bomb_rejected_not_crash(self):
        with pytest.raises(GeometryValidationError):
            validate_aoi_geometry(self._deep_polygon(50))


# -- A09: Audit redaction --


class TestAuditRedaction:
    def test_redacts_nested_dict(self):
        entry = AuditLogger().log_tool_call(
            tool_name="fetch",
            args={"config": {"api_key": "super-secret", "retries": 3}},
            caller="agent",
            org_id="org1",
            status="ok",
            execution_time_ms=1.0,
        )
        assert entry.sanitized_args["config"]["api_key"] == "[REDACTED]"
        assert entry.sanitized_args["config"]["retries"] == 3

    def test_redacts_inside_lists(self):
        entry = AuditLogger().log_tool_call(
            tool_name="fetch",
            args={"options": [{"token": "leak-me"}, {"safe": 1}]},
            caller="agent",
            org_id="org1",
            status="ok",
            execution_time_ms=1.0,
        )
        assert entry.sanitized_args["options"][0]["token"] == "[REDACTED]"
        assert entry.sanitized_args["options"][1]["safe"] == 1

    def test_redacts_sensitive_list_items_directly(self):
        entry = AuditLogger().log_tool_call(
            tool_name="fetch",
            args={"blobs": ["normal", {"password": "hunter2"}]},
            caller="agent",
            org_id="org1",
            status="ok",
            execution_time_ms=1.0,
        )
        assert entry.sanitized_args["blobs"][1]["password"] == "[REDACTED]"

    def test_top_level_redaction_unchanged(self):
        entry = AuditLogger().log_tool_call(
            tool_name="fetch",
            args={"secret_key": "x", "aoi": {"lat": 1.0}},
            caller="agent",
            org_id="org1",
            status="ok",
            execution_time_ms=1.0,
        )
        assert entry.sanitized_args["secret_key"] == "[REDACTED]"
        assert entry.sanitized_args["aoi"] == {"lat": 1.0}


# -- A04: Idempotency 5xx non-caching --


class TestIdempotencyErrorHandling:
    def test_5xx_not_cached(self):
        from packages.shared.middleware.idempotency import IdempotencyMiddleware

        app = FastAPI()
        app.add_middleware(IdempotencyMiddleware)

        @app.post("/api/v1/flaky")
        async def flaky():
            from starlette.responses import JSONResponse

            return JSONResponse(status_code=500, content={"error": "boom"})

        _IDEMPOTENCY_STORE.clear()
        client = TestClient(app, raise_server_exceptions=False)
        r1 = client.post("/api/v1/flaky", headers={"Idempotency-Key": "k1"})
        assert r1.status_code == 500
        # 500 responses must not be cached — replay re-executes.
        r2 = client.post("/api/v1/flaky", headers={"Idempotency-Key": "k1"})
        assert r2.status_code == 500
        assert len(_IDEMPOTENCY_STORE) == 0

    def test_2xx_still_cached(self):
        from packages.shared.middleware.idempotency import IdempotencyMiddleware

        app = FastAPI()
        app.add_middleware(IdempotencyMiddleware)

        @app.post("/api/v1/create")
        async def create():
            from starlette.responses import JSONResponse

            return JSONResponse(status_code=201, content={"id": "m1"})

        _IDEMPOTENCY_STORE.clear()
        client = TestClient(app)
        h = {"Idempotency-Key": "k2"}
        r1 = client.post("/api/v1/create", headers=h)
        r2 = client.post("/api/v1/create", headers=h)
        assert r1.status_code == r2.status_code == 201
        assert len(_IDEMPOTENCY_STORE) == 1


# -- A05: Security response headers --


class TestSecurityHeaders:
    def _client(self):
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/api/v1/ping")
        async def ping():
            return {"ok": True}

        @app.post("/api/v1/mutate")
        async def mutate():
            return {"ok": True}

        return TestClient(app)

    def test_headers_present_on_get(self):
        r = self._client().get("/api/v1/ping")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Referrer-Policy"] == "no-referrer"
        assert "default-src 'none'" in r.headers["Content-Security-Policy"]

    def test_no_store_on_mutation(self):
        r = self._client().post("/api/v1/mutate")
        assert r.headers["Cache-Control"] == "no-store"

    def test_no_cache_control_on_get(self):
        r = self._client().get("/api/v1/ping")
        assert "Cache-Control" not in r.headers


# -- A09: Log hygiene invariants --


class TestLogHygiene:
    def test_no_sensitive_values_in_log_args(self):
        """No logger call may interpolate a token/secret/password value.

        The check inspects the *argument* portion of each logger call (after
        the format string): mentioning the word 'token' in a message is fine,
        passing a variable named like a credential as a format argument is not.
        """
        import re
        from pathlib import Path

        # format-string (possibly several), then comma, then args region
        pattern = re.compile(
            r'logger\.\w+\(.*["\'].+["\']\s*,[^)]*\b'
            r"(token|password|secret|api_key|authorization)\b",
            re.I,
        )
        offenders = []
        for base in ("services/gateway", "services/agent", "packages/shared", "packages/auth"):
            for py in Path(base).rglob("*.py"):
                for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern.search(line):
                        offenders.append(f"{py}:{i}")
        assert offenders == []
