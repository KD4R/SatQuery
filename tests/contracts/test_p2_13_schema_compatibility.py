"""
tests/contracts/test_p2_13_schema_compatibility.py
Contract compatibility tests for P2-13: AcquisitionLoopResult.
"""

import pytest
from services.agent.graph.acquisition_loop import AcquisitionLoopResult


@pytest.mark.contract
def test_p2_13_schema_compatibility():
    """AcquisitionLoopResult schema conforms to contract requirements."""
    schema = AcquisitionLoopResult.model_json_schema()
    expected = {
        "resolved",
        "iterations_run",
        "final_confidence",
        "acquired_observations",
        "history",
    }
    assert expected.issubset(schema["properties"].keys())
