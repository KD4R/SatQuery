"""P1-05 / P1-12: the headers the browser client sends must survive CORS preflight."""

import pytest

from services.gateway.config import GatewaySettings

# Headers apps/web/lib/api/gateway.ts attaches to gateway calls.
CLIENT_HEADERS = {"Authorization", "Content-Type", "X-Trace-Id", "Idempotency-Key"}


@pytest.mark.unit
def test_cors_allows_every_header_the_web_client_sends(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://console.example.org")
    settings = GatewaySettings()
    missing = CLIENT_HEADERS - set(settings.cors_allow_headers)
    assert not missing, f"preflight would reject: {sorted(missing)}"


@pytest.mark.unit
def test_cors_denies_all_origins_by_default(monkeypatch):
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    assert GatewaySettings().cors_allow_origins == []
