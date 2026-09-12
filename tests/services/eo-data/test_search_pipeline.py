import pytest
from datetime import datetime, timezone
import json
from unittest.mock import patch

from services.eo_data.normalization import normalize_stac_item
from services.eo_data.search import SearchService
from services.eo_data.quality import score_observation_quality
from packages.contracts import Observation, SceneRef


def test_normalize_stac_item_fails_on_missing_datetime():
    """P4-06: Normalization pipeline robustly rejects malformed STAC items."""
    malformed_item = {"id": "bad_item", "properties": {}}  # Missing datetime
    with pytest.raises(ValueError, match="missing required 'datetime' property"):
        normalize_stac_item("bhoonidhi", malformed_item)


def test_score_observation_quality_computes_overlap():
    """P4-19: Quality scoring correctly projects to EPSG:32643 and scores geometry."""
    # Create a mock observation
    scene = SceneRef(
        provider="bhoonidhi",
        collection="dummy",
        item_id="1",
        acquired_at=datetime.now(timezone.utc),
        platform="P",
        instrument="SAR",
        href="https://example.com/item.tif",
        cloud_cover=10.0,
        relative_orbit=123,
        pass_direction="ASCENDING",
    )
    obs = Observation(
        observation_id="123",
        scene=scene,
        geometry={
            "type": "Polygon",
            "coordinates": [[[79.8, 15.1], [80.2, 15.1], [80.2, 15.5], [79.8, 15.5], [79.8, 15.1]]],
        },
        assets={},
    )

    aoi_polygon = {
        "type": "Polygon",
        "coordinates": [[[79.8, 15.1], [80.2, 15.1], [80.2, 15.5], [79.8, 15.5], [79.8, 15.1]]],
    }

    # 100% overlap, 10% cloud cover -> score should be 1.0 * 0.9 = 0.9
    score = score_observation_quality(obs, aoi_polygon)
    assert score == pytest.approx(0.9)
    assert obs.normalized_properties["data_quality_score"] == pytest.approx(0.9)


@patch("services.eo_data.search.redis_client")
@patch("services.eo_data.search.BhoonidhiAdapter")
@patch("services.eo_data.search.STACProvider")
def test_search_service_cache_hit(mock_stac, mock_bhoonidhi, mock_redis):
    """P4-07: Search service successfully avoids hitting live APIs when STAC mirror cache hits."""
    service = SearchService()

    # Mock cache hit
    mock_redis.get.return_value = json.dumps(
        [
            {
                "observation_id": "1",
                "scene": {
                    "provider": "bhoonidhi",
                    "collection": "C",
                    "item_id": "I",
                    "acquired_at": "2026-09-10T10:00:00Z",
                    "platform": "P",
                    "instrument": "I",
                    "href": "H",
                    "relative_orbit": 1,
                    "pass_direction": "ASCENDING",
                    "cloud_cover": 0.0,
                },
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "assets": {},
            }
        ]
    )

    obs_list = service.search_observations("bhoonidhi", {}, datetime.now(), datetime.now())

    assert len(obs_list) == 1
    assert obs_list[0].observation_id == "1"

    # Assert providers were not called
    mock_bhoonidhi.return_value.search.assert_not_called()
