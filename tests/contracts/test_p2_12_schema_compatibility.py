"""
tests/contracts/test_p2_12_schema_compatibility.py
Contract compatibility tests for P2-12: DisagreementReport schema.
"""

import pytest
from evidence.disagreement import DisagreementReport


@pytest.mark.contract
def test_p2_12_schema_compatibility():
    """DisagreementReport schema conforms to contract."""
    schema = DisagreementReport.model_json_schema()
    expected = {
        "sar_area_sqkm",
        "optical_area_sqkm",
        "intersection_sqkm",
        "union_sqkm",
        "iou_score",
        "disagreement_percentage",
        "disagreement_area_sqkm",
        "arbitrated_water_area_sqkm",
    }
    assert expected.issubset(schema["properties"].keys())
