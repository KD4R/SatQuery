"""
P6-14 — Prometheus metrics middleware unit tests (no Docker required).

Verifies the in-process part of the monitoring pipeline: the gateway records
latency/counters with bounded label cardinality and exposes them in the exact
families the provisioned Grafana dashboard queries.

All value assertions are *deltas* against a pre-call baseline: Prometheus
counters are cumulative for the life of the process, and the module-level
registry is shared across the test session, so absolute values would be
order-dependent. Deltas mirror how the live QA test (and Grafana's rate()
queries) must read them too.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from packages.observability.metrics import (
    REGISTRY,
    MetricsMiddleware,
    render_metrics,
    route_matches,
)

import pytest

pytestmark = pytest.mark.unit


def _samples(text: str, family: str):
    """Parse exposition text; yield (labels_dict, value) for a metric family."""
    out = []
    for line in text.splitlines():
        if line.startswith(family) and not line.startswith("#"):
            labels_str, _, value = line.partition(" ")
            labels = {}
            for part in labels_str[labels_str.find("{") + 1 : labels_str.rfind("}")].split(","):
                if "=" in part:
                    k, _, v = part.partition("=")
                    labels[k.strip()] = v.strip().strip('"')
            out.append((labels, float(value)))
    return out


def _sample_value(text: str, family: str, **labels) -> float:
    for got_labels, value in _samples(text, family):
        if all(got_labels.get(k) == v for k, v in labels.items()):
            return value
    raise AssertionError(f"No sample for {family} with {labels} in:\n{text[:2000]}")


def _baseline(family: str, **labels) -> float:
    """Current value for a label set, or 0.0 if the series does not exist yet."""
    try:
        return _sample_value(render_metrics().decode(), family, **labels)
    except AssertionError:
        return 0.0


@pytest.fixture()
def client():
    app = FastAPI()
    app.add_middleware(MetricsMiddleware)

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/missions/{mission_id}")
    async def mission(mission_id: str):
        return {"mission_id": mission_id}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False)


class TestMetricsMiddleware:
    def test_successful_request_recorded(self, client):
        before = _baseline("http_server_requests_total", path="/api/v1/health", status="200")
        client.get("/api/v1/health")
        text = render_metrics().decode()
        assert (
            _sample_value(text, "http_server_requests_total", path="/api/v1/health", status="200")
            == before + 1.0
        )

    def test_count_increments_across_requests(self, client):
        before = _baseline("http_server_requests_total", path="/api/v1/health", status="200")
        for _ in range(3):
            client.get("/api/v1/health")
        text = render_metrics().decode()
        assert (
            _sample_value(text, "http_server_requests_total", path="/api/v1/health", status="200")
            == before + 3.0
        )

    def test_histogram_count_and_sum_present(self, client):
        count_before = _baseline(
            "http_server_requests_seconds_count", path="/api/v1/health", status="200"
        )
        sum_before = _baseline(
            "http_server_requests_seconds_sum", path="/api/v1/health", status="200"
        )
        client.get("/api/v1/health")
        text = render_metrics().decode()
        assert (
            _sample_value(
                text, "http_server_requests_seconds_count", path="/api/v1/health", status="200"
            )
            == count_before + 1.0
        )
        # sum must have grown by a positive latency
        assert (
            _sample_value(
                text, "http_server_requests_seconds_sum", path="/api/v1/health", status="200"
            )
            > sum_before
        )

    def test_bucket_series_exist(self, client):
        client.get("/api/v1/health")
        text = render_metrics().decode()
        buckets = [labels for labels, _ in _samples(text, "http_server_requests_seconds_bucket")]
        assert any(labels.get("le") == "+Inf" for labels in buckets)
        assert any(labels.get("le") == "0.005" for labels in buckets)

    def test_error_status_recorded(self, client):
        """A 404 must be counted under its own status label."""
        path_404 = "/definitely-not-a-route-p6-14"
        before = _baseline("http_server_requests_total", path=path_404, status="404")
        client.get(path_404)
        text = render_metrics().decode()
        assert (
            _sample_value(text, "http_server_requests_total", path=path_404, status="404")
            == before + 1.0
        )

    def test_unhandled_exception_counted_as_500(self, client):
        before = _baseline("http_server_requests_total", path="/boom", status="500")
        client.get("/boom")
        text = render_metrics().decode()
        assert (
            _sample_value(text, "http_server_requests_total", path="/boom", status="500")
            == before + 1.0
        )

    def test_templated_path_not_raw_id(self, client):
        """Distinct mission IDs must collapse onto one template series."""
        template_before = _baseline(
            "http_server_requests_total", path="/api/v1/missions/{mission_id}", status="200"
        )
        for mid in ("alpha", "beta", "gamma", "delta"):
            client.get(f"/api/v1/missions/{mid}")
        text = render_metrics().decode()
        assert (
            _sample_value(
                text,
                "http_server_requests_total",
                path="/api/v1/missions/{mission_id}",
                status="200",
            )
            == template_before + 4.0
        )
        # And no raw-ID series may exist
        assert '/api/v1/missions/alpha"' not in text

    def test_exposition_format_is_prometheus_text(self, client):
        """render_metrics() must return parseable Prometheus text exposition."""
        client.get("/api/v1/health")
        raw = render_metrics()
        assert isinstance(raw, bytes)
        assert b"# HELP http_server_requests_seconds" in raw
        assert b"# TYPE http_server_requests_seconds histogram" in raw

    def test_metric_names_match_dashboard_queries(self, client):
        """The dashboard queries exactly these families — names are a contract."""
        client.get("/api/v1/health")
        text = render_metrics().decode()
        assert "http_server_requests_seconds_count" in text
        assert "http_server_requests_seconds_bucket" in text
        assert "http_server_requests_total" in text


class TestRouteMatching:
    def test_exact_match(self):
        assert route_matches("/api/v1/health", "/api/v1/health")

    def test_param_match(self):
        assert route_matches("/api/v1/missions/m-123", "/api/v1/missions/{mission_id}")

    def test_param_rejects_empty(self):
        assert not route_matches("/api/v1/missions/", "/api/v1/missions/{mission_id}")

    def test_segment_count_mismatch(self):
        assert not route_matches("/api/v1/missions/m-1/extra", "/api/v1/missions/{mission_id}")

    def test_prefix_is_not_match(self):
        assert not route_matches("/api/v1/missions", "/api/v1/missions/{mission_id}")


class TestRegistryHygiene:
    def test_registry_is_isolated(self):
        """Module registry is not the prometheus_client global default."""
        from prometheus_client import REGISTRY as GLOBAL_REGISTRY

        assert REGISTRY is not GLOBAL_REGISTRY

    def test_collectors_registered(self):
        names = set(REGISTRY._names_to_collectors.keys())
        assert "http_server_requests_seconds" in names
        assert "http_server_requests_total" in names
