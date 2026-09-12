"""
tests/contracts/test_p2_07_schema_compatibility.py
Contract compatibility tests for P2-07: STACSearchArgs and AssetSelectorArgs.
"""

import pytest
from services.agent.tools.asset_selector import AssetSelectorArgs
from services.agent.tools.stac_search import STACSearchArgs


@pytest.mark.contract
def test_p2_07_schema_compatibility():
    """STAC search and asset selector args schemas conform to contracts."""
    stac_schema = STACSearchArgs.model_json_schema()
    assert {"bbox", "start_date", "end_date", "sensors", "max_cloud_cover"}.issubset(
        stac_schema["properties"].keys()
    )

    selector_schema = AssetSelectorArgs.model_json_schema()
    assert {"assets", "preferred_sensor", "max_cloud_cover"}.issubset(
        selector_schema["properties"].keys()
    )
