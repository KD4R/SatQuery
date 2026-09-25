import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from packages.contracts.ml import Observation, SceneRef


def _make_dummy_obs(sensor: str, cloud_cover: float, obs_id: str | None = None) -> Observation:
    return Observation(
        observation_id=obs_id or str(uuid.uuid4()),
        scene=SceneRef(
            provider="bhoonidhi",
            collection="S1_IW_GRDH",
            item_id=f"SCENE_{sensor}_{uuid.uuid4().hex[:6]}",
            acquired_at=datetime(2026, 9, 2, 0, 35, 12, tzinfo=timezone.utc),
            platform="Sentinel-1A",
            instrument="C-SAR" if sensor == "S1_SAR" else "MSI",
            relative_orbit=None,
            pass_direction=None,
            href=f"s3://satquery/{sensor.lower()}_scene.tif",
            cloud_cover=cloud_cover if sensor != "S1_SAR" else None,
        ),
        geometry={
            "type": "Polygon",
            "coordinates": [[[92.0, 25.5], [94.0, 25.5], [94.0, 27.5], [92.0, 27.5], [92.0, 25.5]]],
        },
        assets={"vv": f"s3://satquery/{sensor.lower()}_vv.tif"},
        normalized_properties={"sensor": sensor, "cloud_cover": cloud_cover},
    )


@pytest.fixture(autouse=True)
def mock_agent_dependencies_for_integration_tests():
    """
    Globally mock the STAC search provider and Inference client during integration tests.
    Since we removed the CELERY_TASK_ALWAYS_EAGER fallback in stac_search.py and orchestrator.py,
    the agent actually attempts to hit Bhoonidhi and Inference services, which fails in the CI environment
    due to missing credentials or network isolation.
    """
    sar_obs = _make_dummy_obs("S1_SAR", 0.0)
    opt_obs = _make_dummy_obs("S2_OPTICAL", 14.5)

    async def mock_post(self, url, *args, **kwargs):
        class MockResponse:
            def json(self):
                return {
                    "measurements": [{"name": "flood_extent_ha", "value": 14250.0}],
                    "degraded_from": "baseline"
                }
            def raise_for_status(self): pass
        return MockResponse()

    with patch(
        "services.eo_data.search.SearchService.search_observations",
        return_value=[sar_obs, opt_obs],
    ), patch(
        "packages.shared.client.InternalClient.post",
        new=mock_post
    ):
        yield
