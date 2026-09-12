"""
tests/contracts/test_p2_11_schema_compatibility.py
Contract compatibility tests for P2-11: ConfidenceRequest and ConfidenceResponse.
"""

import pytest
from packages.contracts.agent import ConfidenceRequest, ConfidenceResponse


@pytest.mark.contract
def test_p2_11_schema_compatibility():
    """ConfidenceRequest and ConfidenceResponse schemas conform to contract."""
    req_schema = ConfidenceRequest.model_json_schema()
    assert {"evidence_nodes", "sensor_type", "cloud_cover", "resolution_meters"}.issubset(
        req_schema["properties"].keys()
    )

    resp_schema = ConfidenceResponse.model_json_schema()
    assert {"confidence_score", "passed_gate", "uncertainty_factors", "action"}.issubset(
        resp_schema["properties"].keys()
    )
