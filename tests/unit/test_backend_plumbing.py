"""Plumbing fixes behind the live dashboard: client timeouts, dev sign-in,
collection selection, and signing Planetary Computer hrefs after the cache."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from packages.auth.models import AuthContext, Role


def _ctx():
    return AuthContext(
        subject="t", organisation_id="org", roles=[Role.SYSTEM], email=None, trace_id="t"
    )


# ── InternalClient ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_internal_client_timeout_and_attempts_are_configurable(monkeypatch):
    from packages.shared import client as client_mod

    monkeypatch.setattr(client_mod, "generate_s2s_token", lambda **_: "tok")
    c = client_mod.InternalClient("http://x", "agent", [], timeout=180, max_attempts=1)
    assert c.client.timeout.read == 180

    calls = {"n": 0}

    async def boom(*a, **k):
        calls["n"] += 1
        raise httpx.ReadTimeout("slow")

    c.client.request = boom
    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(c.post("/p", auth_context=_ctx()))
    assert calls["n"] == 1  # no silent re-run of an expensive call

    d = client_mod.InternalClient("http://x", "agent", [])
    assert d.client.timeout.read == 5.0 and d.max_attempts == 3
    with pytest.raises(ValueError):
        client_mod.InternalClient("http://x", "agent", [], max_attempts=0)


# ── Dev sign-in ──────────────────────────────────────────────────────────────


def _dev_app():
    from fastapi import FastAPI

    from services.gateway.routers.dev_auth import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.unit
def test_dev_token_is_off_unless_explicitly_enabled(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SATQUERY_DEV_LOGIN", "1")
    monkeypatch.setenv("AUTH_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_SECRET_KEY", "s")
    assert TestClient(_dev_app()).post("/api/v1/auth/dev-token").status_code == 404
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SATQUERY_DEV_LOGIN", "0")
    assert TestClient(_dev_app()).post("/api/v1/auth/dev-token").status_code == 404


@pytest.mark.unit
def test_dev_token_verifies_through_the_normal_path(monkeypatch):
    from fastapi.testclient import TestClient

    from packages.auth import config as auth_config
    from packages.auth.dependencies import _build_auth_context
    from packages.auth.jwt import decode_and_verify

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SATQUERY_DEV_LOGIN", "1")
    monkeypatch.setenv("AUTH_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_SECRET_KEY", "dev-secret")
    monkeypatch.setenv("SATQUERY_DEV_ORG_ID", "org-local")
    monkeypatch.delenv("AUTH_AUDIENCE", raising=False)
    monkeypatch.delenv("AUTH_ISSUER", raising=False)
    if hasattr(auth_config.get_auth_settings, "cache_clear"):
        auth_config.get_auth_settings.cache_clear()
    monkeypatch.setattr(auth_config, "_settings", None, raising=False)

    r = TestClient(_dev_app()).post("/api/v1/auth/dev-token", json={"email": "me@example.com"})
    assert r.status_code == 200, r.text
    body = r.json()
    ctx = _build_auth_context(decode_and_verify(body["access_token"]))
    assert ctx.organisation_id == "org-local"
    assert ctx.has_role(Role.ANALYST)


# ── STAC tool: collections follow the requested sensors ─────────────────────


@pytest.mark.unit
def test_stac_search_queries_only_requested_collections(monkeypatch):
    from services.agent.tools import stac_search

    seen = {}

    def fake_search(**kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(stac_search.search_service, "search_observations", fake_search)
    tool = stac_search.STACSearchTool()
    res = tool.execute(
        bbox=[92, 26, 93, 27],
        start_date="2024-07-01T00:00:00Z",
        end_date="2024-07-10T00:00:00Z",
        sensors=["S1_SAR"],
    )
    assert res.success
    assert seen["collections"] == ["sentinel-1-rtc"]


# ── Signing after the cache ──────────────────────────────────────────────────


@pytest.mark.unit
def test_planetary_computer_hrefs_are_signed_on_every_read(monkeypatch):
    import planetary_computer

    from packages.contracts import Observation, SceneRef
    from services.eo_data.search import SearchService

    obs = Observation(
        observation_id="o1",
        scene=SceneRef(
            provider="planetary_computer",
            collection="sentinel-1-rtc",
            item_id="o1",
            acquired_at=datetime(2024, 7, 4, tzinfo=timezone.utc),
            platform="SENTINEL-1A",
            instrument="C-SAR",
            relative_orbit=None,
            pass_direction=None,
            href="https://x/o1",
        ),
        geometry={"type": "Point", "coordinates": [0, 0]},
        assets={"vv": "https://sentinel1euwestrtc.blob.core.windows.net/a/vv.tif"},
    )
    monkeypatch.setattr(planetary_computer, "sign", lambda href: href + "?sig=fresh")
    signed = SearchService._signed("planetary_computer", [obs])
    assert signed[0].assets["vv"].endswith("?sig=fresh")
    assert obs.assets["vv"].endswith("vv.tif")  # the cached copy stays unsigned
    assert SearchService._signed("bhoonidhi", [obs])[0] is obs
