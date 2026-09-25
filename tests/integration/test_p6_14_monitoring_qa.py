"""
P6-14 — Monitoring/report integration QA

Validates that the full observability pipeline is correctly wired:
services → OTel collector → Prometheus → Grafana dashboards.

The ``TestLivePrometheusMetrics`` class is the live end-to-end QA from the
P6 plan: it starts the api + prometheus services, generates real HTTP traffic
against the gateway, then asserts via the Prometheus query API
(``/api/v1/query``) that ``http_server_requests_*`` actually incremented —
i.e. scrape → storage → query all work, not just that config files exist.

Requires Docker; skips cleanly when Docker is unavailable.
"""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration

INFRA_DIR = Path("infrastructure/docker")
COMPOSE_FILE = INFRA_DIR / "docker-compose.yml"

PROM_PORT = os.getenv("PROMETHEUS_PORT", "9090")
API_PORT = os.getenv("API_PORT", "8000")
PROM_BASE = f"http://localhost:{PROM_PORT}"
API_BASE = f"http://localhost:{API_PORT}"

#: How long to wait for a scrape to land after traffic is generated.
SCRAPE_WAIT_S = 20
#: Prometheus scrape interval for the satquery-api job (prometheus.yml).
API_SCRAPE_INTERVAL_S = 10


def _get(url: str, timeout: float = 10.0):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode()


def _prom_query(expr: str):
    """Execute an instant query against the Prometheus query API."""
    from urllib.parse import urlencode

    url = f"{PROM_BASE}/api/v1/query?{urlencode({'query': expr})}"
    status, body = _get(url)
    assert status == 200, f"Prometheus query failed: {status} {body[:200]}"
    data = json.loads(body)
    assert data["status"] == "success", f"Prometheus query error: {data}"
    return data["data"]["result"]


def _prom_ready(timeout: float = 90.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status, _ = _get(f"{PROM_BASE}/-/ready", timeout=3.0)
            if status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1.0)
    return False


def _api_ready(timeout: float = 120.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status, _ = _get(f"{API_BASE}/api/v1/health", timeout=3.0)
            if status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1.0)
    return False


def _target_up(timeout: float = 60.0) -> bool:
    """Wait until Prometheus reports the satquery-api target as up."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = _prom_query('up{job="satquery-api"}')
            for series in result:
                if int(float(series["value"][1])) == 1:
                    return True
        except (AssertionError, urllib.error.URLError, OSError):
            pass
        time.sleep(2.0)
    return False


def _compose(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


INFRA_DIR = Path("infrastructure/docker")


class TestOTelCollectorPipeline:
    """Verify OTel collector config feeds into Prometheus."""

    def test_otel_receives_otlp(self):
        with open(INFRA_DIR / "otel-collector-config.yml") as f:
            data = yaml.safe_load(f)
        assert "otlp" in data["receivers"]
        assert "grpc" in data["receivers"]["otlp"]["protocols"]
        assert "http" in data["receivers"]["otlp"]["protocols"]

    def test_otel_exports_to_prometheus(self):
        with open(INFRA_DIR / "otel-collector-config.yml") as f:
            data = yaml.safe_load(f)
        assert "prometheus" in data["exporters"]

    def test_otel_has_traces_pipeline(self):
        with open(INFRA_DIR / "otel-collector-config.yml") as f:
            data = yaml.safe_load(f)
        pipelines = data["service"]["pipelines"]
        assert "traces" in pipelines
        assert "otlp" in pipelines["traces"]["receivers"]
        assert "logging" in pipelines["traces"]["exporters"]

    def test_otel_has_metrics_pipeline(self):
        with open(INFRA_DIR / "otel-collector-config.yml") as f:
            data = yaml.safe_load(f)
        pipelines = data["service"]["pipelines"]
        assert "metrics" in pipelines
        assert "prometheus" in pipelines["metrics"]["exporters"]


class TestPrometheusScrapePipeline:
    """Verify Prometheus scrapes the right targets."""

    def test_scrapes_api_metrics(self):
        with open(INFRA_DIR / "prometheus.yml") as f:
            data = yaml.safe_load(f)
        jobs = {j["job_name"]: j for j in data["scrape_configs"]}
        assert "satquery-api" in jobs
        assert jobs["satquery-api"].get("metrics_path") == "/metrics"

    def test_scrapes_otel_collector(self):
        with open(INFRA_DIR / "prometheus.yml") as f:
            data = yaml.safe_load(f)
        jobs = {j["job_name"]: j for j in data["scrape_configs"]}
        assert "otel-collector" in jobs

    def test_scrape_interval_reasonable(self):
        with open(INFRA_DIR / "prometheus.yml") as f:
            data = yaml.safe_load(f)
        interval = data["global"]["scrape_interval"]
        assert interval.endswith("s")


class TestGrafanaIntegration:
    """Verify Grafana is configured to query Prometheus."""

    def test_datasource_points_to_prometheus(self):
        with open(INFRA_DIR / "grafana/datasources/datasources.yml") as f:
            data = yaml.safe_load(f)
        for ds in data["datasources"]:
            if ds["type"] == "prometheus":
                assert "prometheus" in ds["url"]

    def test_dashboard_provisioning_configured(self):
        with open(INFRA_DIR / "grafana/dashboards/dashboards.yml") as f:
            data = yaml.safe_load(f)
        assert len(data["providers"]) > 0
        assert data["providers"][0]["type"] == "file"

    def test_dashboard_json_has_panels(self):
        dashboard_path = INFRA_DIR / "grafana/dashboards/satquery-overview.json"
        assert dashboard_path.exists()
        with open(dashboard_path) as f:
            data = json.load(f)
        assert len(data["panels"]) >= 5


class TestDockerComposeObservability:
    """Verify Docker Compose wires observability services together."""

    def test_api_connects_to_otel(self):
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        api_env = data["services"]["api"]["environment"]
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in api_env
        assert "otel-collector" in api_env["OTEL_EXPORTER_OTLP_ENDPOINT"]

    def test_otel_collector_service_exists(self):
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        assert "otel-collector" in data["services"]

    def test_prometheus_service_exists(self):
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        assert "prometheus" in data["services"]

    def test_grafana_service_exists(self):
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        assert "grafana" in data["services"]


class TestP614ServiceBoundary:
    def test_no_service_imports_from_tests(self):
        """Service code must not import from test modules."""
        infra_dir = Path("infrastructure/docker")
        for py_file in infra_dir.glob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            content = py_file.read_text(errors="ignore")
            assert "from tests" not in content, f"{py_file} imports from tests"


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.fixture(scope="module")
def live_observability_stack():
    """Start api + prometheus (+ deps), wait for readiness, then tear down.

    Only the services the QA needs are started; the full stack (web, grafana,
    workers) is unnecessary and slower.
    """
    if not _docker_available():
        pytest.skip("Docker is not available — skipping live monitoring QA")

    up = _compose("up", "-d", "--build", "postgres", "redis", "api", "prometheus", timeout=600)
    if up.returncode != 0:
        pytest.fail(f"Failed to start observability stack: {up.stderr[-500:]}")

    if not _api_ready():
        pytest.fail("Gateway did not become healthy in time")
    if not _prom_ready():
        pytest.fail("Prometheus did not become ready in time")
    if not _target_up():
        pytest.fail("Prometheus never reported satquery-api target up")

    yield {"prom_base": PROM_BASE, "api_base": API_BASE}

    # Leave the stack running if we started nothing? No — down to keep the
    # host clean, but keep volumes so other suites are unaffected.
    _compose("down", "--remove-orphans")


class TestLivePrometheusMetrics:
    """Live QA: traffic → gateway counters → Prometheus scrape → query API.

    This is the P6-14 acceptance test from the plan: trigger a sequence of
    API calls, then assert via ``/api/v1/query`` that the corresponding
    metrics actually incremented.
    """

    def test_request_counter_increments_in_prometheus(self, live_observability_stack):
        """Generate traffic, wait for a scrape, assert the counter grew."""
        expr = 'http_server_requests_total{job="satquery-api",path="/api/v1/health",status="200"}'

        before = sum(int(float(s["value"][1])) for s in _prom_query(expr))

        # Trigger a known number of requests through the real gateway.
        hits = 5
        for _ in range(hits):
            status, _ = _get(f"{API_BASE}/api/v1/health")
            assert status == 200

        # Wait for the next scrape of the satquery-api job to land.
        deadline = time.monotonic() + SCRAPE_WAIT_S + API_SCRAPE_INTERVAL_S
        after = before
        scraped = False
        while time.monotonic() < deadline:
            time.sleep(2.0)
            after = sum(int(float(s["value"][1])) for s in _prom_query(expr))
            if after >= before + hits:
                scraped = True
                break

        assert scraped, (
            f"Prometheus did not reflect {hits} new requests: before={before}, after={after}. "
            "Check scrape config, gateway /metrics endpoint, and network wiring."
        )

    def test_error_rate_series_available(self, live_observability_stack):
        """The dashboard's error-rate math must have a non-empty result.

        rate() needs >= 2 samples in its window, so poll until the second
        scrape of the satquery-api job has landed (interval is 10s).
        """
        expr = 'sum(rate(http_server_requests_seconds_count{job="satquery-api"}[5m]))'
        deadline = time.monotonic() + API_SCRAPE_INTERVAL_S * 3 + SCRAPE_WAIT_S
        result = []
        while time.monotonic() < deadline:
            result = _prom_query(expr)
            if result:
                break
            time.sleep(2.0)
        assert result, "http_server_requests_seconds_count series missing from Prometheus"

    def test_latency_histogram_quantile_queryable(self, live_observability_stack):
        """Dashboard latency panels use histogram_quantile — it must work."""
        expr = (
            "histogram_quantile(0.95, "
            'sum by (le) (rate(http_server_requests_seconds_bucket{job="satquery-api"}[5m])))'
        )
        deadline = time.monotonic() + API_SCRAPE_INTERVAL_S * 3 + SCRAPE_WAIT_S
        result = []
        while time.monotonic() < deadline:
            result = _prom_query(expr)
            if result:
                break
            time.sleep(2.0)
        assert result, "histogram_quantile over latency buckets returned no data"

    def test_gateway_metrics_endpoint_matches_prometheus(self, live_observability_stack):
        """/metrics families on the gateway must be the ones Prometheus stores."""
        status, body = _get(f"{API_BASE}/metrics")
        assert status == 200
        assert "http_server_requests_seconds" in body
        # And Prometheus must know the target is healthy.
        result = _prom_query('up{job="satquery-api"}')
        assert any(int(float(s["value"][1])) == 1 for s in result)
