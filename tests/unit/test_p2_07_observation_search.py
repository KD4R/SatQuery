"""
tests/unit/test_p2_07_observation_search.py
Unit tests for P2-07: Observation search and asset selection tools.
"""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from pydantic import ValidationError
from services.agent.tools.asset_selector import AssetSelectorTool
from services.agent.tools.stac_search import STACSearchTool
from packages.contracts.ml import Observation, SceneRef


def _make_obs(sensor: str, cloud_cover: float, obs_id: str | None = None) -> Observation:
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


@pytest.mark.unit
def test_observation_search_and_asset_selection_tools_valid():
    """STAC search finds scenes and asset selector filters/ranks by sensor & cloud cover."""
    sar_obs = _make_obs("S1_SAR", 0.0)
    opt_obs = _make_obs("S2_OPTICAL", 14.5)

    with patch(
        "services.agent.tools.stac_search.search_service.search_observations",
        return_value=[sar_obs, opt_obs],
    ):
        stac_tool = STACSearchTool()
        search_res = stac_tool.execute(
            bbox=[92.0, 25.5, 94.0, 27.5],
            start_date="2026-09-01T00:00:00Z",
            end_date="2026-09-05T00:00:00Z",
            sensors=["S1_SAR", "S2_OPTICAL"],
            max_cloud_cover=25.0,
        )

    assert search_res.success is True
    scenes = search_res.output
    assert len(scenes) >= 2
    assert any(s["sensor"] == "S1_SAR" for s in scenes)

    selector_tool = AssetSelectorTool()
    select_res = selector_tool.execute(
        assets=scenes,
        preferred_sensor="S1_SAR",
        max_cloud_cover=20.0,
    )
    assert select_res.success is True
    selected = select_res.output
    # S1_SAR should be ranked first
    assert selected[0]["sensor"] == "S1_SAR"


@pytest.mark.unit
def test_observation_search_and_asset_selection_tools_invalid_input():
    """Out-of-bounds coordinates, bad bbox size, and invalid cloud cover raise errors."""
    stac_tool = STACSearchTool()

    # Out-of-bounds longitude (> 180)
    with pytest.raises(ValueError, match="Longitude out of bounds"):
        stac_tool.execute(
            bbox=[195.0, 25.5, 94.0, 27.5],
            start_date="2026-09-01T00:00:00Z",
            end_date="2026-09-05T00:00:00Z",
        )

    # Incomplete bbox (needs 4 elements)
    with pytest.raises(ValidationError):
        stac_tool.execute(
            bbox=[92.0, 25.5],
            start_date="2026-09-01T00:00:00Z",
            end_date="2026-09-05T00:00:00Z",
        )

    # Asset selector negative cloud cover fails schema validation
    selector_tool = AssetSelectorTool()
    with pytest.raises(ValidationError):
        selector_tool.execute(
            assets=[],
            max_cloud_cover=-10.0,
        )
