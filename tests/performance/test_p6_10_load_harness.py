"""
P6-10 — Performance/load test harness

Validates performance under load by sending concurrent requests
to the Docker Compose environment. Tests fail if P95 latency exceeds
thresholds or if error rates rise.
"""

import asyncio
import time
from pathlib import Path

import httpx
import pytest

from infrastructure.docker.implementation import check_service_health

pytestmark = [pytest.mark.performance, pytest.mark.integration]


# -- Performance Thresholds --
MAX_P95_LATENCY_MS = 2000  # 2 seconds
MAX_ERROR_RATE_PCT = 5.0
CONCURRENT_REQUESTS = 20


@pytest.mark.asyncio
async def test_api_load_performance(docker_available, compose_env):
    """API must handle concurrent load with P95 latency < 2s and < 5% error rate."""
    assert check_service_health("api"), "API Gateway must be healthy before load test"

    async def fetch(client: httpx.AsyncClient):
        start_time = time.monotonic()
        try:
            # Hit the health endpoint to simulate basic load
            resp = await client.get("/api/v1/health")
            elapsed_ms = (time.monotonic() - start_time) * 1000
            return (resp.status_code, elapsed_ms)
        except Exception:
            return (500, (time.monotonic() - start_time) * 1000)

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=5.0) as client:
        tasks = [fetch(client) for _ in range(CONCURRENT_REQUESTS)]
        results = await asyncio.gather(*tasks)

    # Analyze results
    errors = sum(1 for status, _ in results if status != 200)
    latencies = sorted([lat for _, lat in results])

    error_rate = (errors / CONCURRENT_REQUESTS) * 100
    p95_index = int(len(latencies) * 0.95) - 1
    p95_latency = latencies[max(0, p95_index)]

    assert (
        error_rate <= MAX_ERROR_RATE_PCT
    ), f"Error rate {error_rate}% exceeds max {MAX_ERROR_RATE_PCT}%"
    assert (
        p95_latency <= MAX_P95_LATENCY_MS
    ), f"P95 latency {p95_latency:.2f}ms exceeds max {MAX_P95_LATENCY_MS}ms"


# -- Service Boundary --


class TestP610ServiceBoundary:
    def test_no_service_imports_from_tests(self):
        """Performance test code must not import from service modules."""
        for py_file in Path("tests/performance").glob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            content = py_file.read_text(errors="ignore")
            assert "from services" not in content
            assert "from packages" not in content
