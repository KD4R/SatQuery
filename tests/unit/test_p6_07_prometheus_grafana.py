"""
P6-07 — Prometheus metrics and Grafana dashboards

Validates that Prometheus and Grafana configs are correctly structured,
the Grafana dashboard JSON is valid, and the OTel collector exports
to Prometheus.
"""

import json
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

INFRA_DIR = Path("infrastructure/docker")
PROMETHEUS_YML = INFRA_DIR / "prometheus.yml"
GRAFANA_DATASOURCES = INFRA_DIR / "grafana" / "datasources" / "datasources.yml"
GRAFANA_DASHBOARDS = INFRA_DIR / "grafana" / "dashboards" / "dashboards.yml"
GRAFANA_DASHBOARD_JSON = INFRA_DIR / "grafana" / "dashboards" / "satquery-overview.json"
OTEL_CONFIG = INFRA_DIR / "otel-collector-config.yml"


# -- Prometheus Config --


class TestPrometheusConfig:
    def test_prometheus_yml_exists(self):
        assert PROMETHEUS_YML.exists(), "prometheus.yml must exist"

    def test_valid_yaml(self):
        with open(PROMETHEUS_YML) as f:
            data = yaml.safe_load(f)
        assert "global" in data
        assert "scrape_configs" in data

    def test_scrape_interval_set(self):
        with open(PROMETHEUS_YML) as f:
            data = yaml.safe_load(f)
        assert "scrape_interval" in data["global"]

    def test_scrapes_api(self):
        with open(PROMETHEUS_YML) as f:
            data = yaml.safe_load(f)
        job_names = [job["job_name"] for job in data["scrape_configs"]]
        assert "satquery-api" in job_names

    def test_scrapes_otel_collector(self):
        with open(PROMETHEUS_YML) as f:
            data = yaml.safe_load(f)
        job_names = [job["job_name"] for job in data["scrape_configs"]]
        assert "otel-collector" in job_names

    def test_scrapes_prometheus_self(self):
        with open(PROMETHEUS_YML) as f:
            data = yaml.safe_load(f)
        job_names = [job["job_name"] for job in data["scrape_configs"]]
        assert "prometheus" in job_names


# -- Grafana Config --


class TestGrafanaDatasources:
    def test_datasources_yml_exists(self):
        assert GRAFANA_DATASOURCES.exists()

    def test_valid_yaml(self):
        with open(GRAFANA_DATASOURCES) as f:
            data = yaml.safe_load(f)
        assert "datasources" in data

    def test_prometheus_datasource_configured(self):
        with open(GRAFANA_DATASOURCES) as f:
            data = yaml.safe_load(f)
        names = [ds["name"] for ds in data["datasources"]]
        assert "Prometheus" in names

    def test_prometheus_url_points_to_prometheus_service(self):
        with open(GRAFANA_DATASOURCES) as f:
            data = yaml.safe_load(f)
        for ds in data["datasources"]:
            if ds["name"] == "Prometheus":
                assert "prometheus" in ds["url"]


class TestGrafanaDashboards:
    def test_dashboards_yml_exists(self):
        assert GRAFANA_DASHBOARDS.exists()

    def test_valid_yaml(self):
        with open(GRAFANA_DASHBOARDS) as f:
            data = yaml.safe_load(f)
        assert "providers" in data
        assert len(data["providers"]) > 0

    def test_dashboard_json_exists(self):
        assert GRAFANA_DASHBOARD_JSON.exists(), "satquery-overview.json must exist"

    def test_dashboard_json_valid(self):
        with open(GRAFANA_DASHBOARD_JSON) as f:
            data = json.load(f)
        assert "panels" in data
        assert "title" in data
        assert data["title"] == "SatQuery API Overview"

    def test_dashboard_has_panels(self):
        with open(GRAFANA_DASHBOARD_JSON) as f:
            data = json.load(f)
        assert len(data["panels"]) >= 5, "Dashboard should have at least 5 panels"

    def test_dashboard_has_api_latency_panel(self):
        with open(GRAFANA_DASHBOARD_JSON) as f:
            data = json.load(f)
        titles = [p.get("title", "") for p in data["panels"]]
        assert any("Latency" in t for t in titles), "Missing API latency panel"

    def test_dashboard_has_error_rate_panel(self):
        with open(GRAFANA_DASHBOARD_JSON) as f:
            data = json.load(f)
        titles = [p.get("title", "") for p in data["panels"]]
        assert any("Error" in t for t in titles), "Missing error rate panel"


# -- OTel -> Prometheus Pipeline --


class TestOTelPrometheusPipeline:
    def test_otel_collector_exports_to_prometheus(self):
        with open(OTEL_CONFIG) as f:
            data = yaml.safe_load(f)
        assert "prometheus" in data["exporters"]

    def test_otel_traces_pipeline_exists(self):
        with open(OTEL_CONFIG) as f:
            data = yaml.safe_load(f)
        assert "traces" in data["service"]["pipelines"]

    def test_otel_metrics_pipeline_exists(self):
        with open(OTEL_CONFIG) as f:
            data = yaml.safe_load(f)
        assert "metrics" in data["service"]["pipelines"]


# -- Service Boundary --


class TestP607ServiceBoundary:
    def test_no_service_imports_from_tests(self):
        """Monitoring code must not import from test modules."""
        for py_file in INFRA_DIR.glob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            content = py_file.read_text(errors="ignore")
            assert "from tests" not in content, f"{py_file} imports from tests"
            assert "import tests" not in content, f"{py_file} imports tests"
