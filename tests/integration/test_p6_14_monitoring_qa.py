"""
P6-14 — Monitoring/report integration QA

Validates that the full observability pipeline is correctly wired:
services → OTel collector → Prometheus → Grafana dashboards.
"""

import json
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration

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
        assert "prometheus" in pipelines["traces"]["exporters"]

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
