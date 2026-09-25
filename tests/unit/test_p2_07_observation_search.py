"""
tests/unit/test_p2_07_observation_search.py
Unit tests for P2-07: Observation search and asset selection tools.
"""

import pytest
from pydantic import ValidationError
from services.agent.tools.asset_selector import AssetSelectorTool
from services.agent.tools.stac_search import STACSearchTool


from unittest.mock import patch, MagicMock


@pytest.mark.unit
@patch("services.agent.tools.stac_search.search_service.search_observations")
def test_observation_search_and_asset_selection_tools_valid(mock_search):
    """STAC search finds scenes and asset selector filters/ranks by sensor & cloud cover."""
    mock_obs_1 = MagicMock()
    mock_obs_1.sensor = "S1_SAR"
    mock_obs_1.model_dump.return_value = {"sensor": "S1_SAR", "cloud_cover": 0.0, "asset_id": "1"}

    mock_obs_2 = MagicMock()
    mock_obs_2.sensor = "S2_OPTICAL"
    mock_obs_2.model_dump.return_value = {
        "sensor": "S2_OPTICAL",
        "cloud_cover": 10.0,
        "asset_id": "2",
    }

    mock_search.return_value = [mock_obs_1, mock_obs_2]

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
