import pytest
import json
from unittest.mock import patch

from services.geo.recovery import FixtureFallbackManager
from services.geo.worker import process_geo_job


def test_fixture_fallback_manager_loads_valid_fixture(tmp_path):
    """P4-17: Verifies fallback manager accurately loads pinned JSON fixtures when APIs fail."""
    # Setup dummy fixture file
    fixture_dir = tmp_path / "recorded"
    fixture_dir.mkdir()
    fixture_file = fixture_dir / "bhoonidhi_sample.json"
    fixture_file.write_text(json.dumps({"features": []}))

    manager = FixtureFallbackManager(fixture_dir=str(fixture_dir))
    data = manager.recover_search("bhoonidhi_sample")

    assert data == {"features": []}


def test_fixture_fallback_manager_raises_on_missing(tmp_path):
    manager = FixtureFallbackManager(fixture_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="Fallback fixture not found"):
        manager.recover_search("missing_fixture")


@patch("services.geo.worker.redis_client")
def test_async_geojob_worker_idempotency(mock_redis):
    """P4-16: Verifies Celery Async GeoJob worker honors Redis SETNX locks to prevent duplicate heavy ML jobs."""  # noqa: E501
    # Simulate job already running/completed
    mock_redis.set.return_value = False

    # Call the celery task directly (as a Python function)
    result = process_geo_job("job_123", "idemp_abc", {})

    assert result["status"] == "skipped"
    assert result["reason"] == "idempotency_key_exists"
