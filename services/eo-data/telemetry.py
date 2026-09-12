from opentelemetry import trace
from prometheus_client import Histogram, Counter
from typing import Dict

tracer = trace.get_tracer("satquery.eo_data")

geo_search_latency_ms = Histogram(
    "geo_search_latency_ms", "Latency of geospatial metadata searches"
)

geo_job_duration_ms = Histogram("geo_job_duration_ms", "Duration of asynchronous geospatial jobs")

asset_download_failure_total = Counter(
    "asset_download_failure_total", "Total number of failed asset downloads"
)

raster_validation_failure_total = Counter(
    "raster_validation_failure_total", "Total number of raster validation failures"
)


def inject_context_to_span(span, context: Dict[str, str]):
    """Standardize OpenTelemetry context propagation across P4 modules."""
    for key in ["trace_id", "mission_id", "run_id", "job_id", "organization_id"]:
        if val := context.get(key):
            span.set_attribute(f"satquery.{key}", val)
