"""
tests/contracts/test_p2_14_schema_compatibility.py
Contract compatibility tests for P2-14: SynthesizedOutput.
"""

import pytest
from services.agent.nodes.synthesizer import SynthesizedOutput


@pytest.mark.contract
def test_p2_14_schema_compatibility():
    """SynthesizedOutput schema conforms to contract requirements."""
    schema = SynthesizedOutput.model_json_schema()
    expected = {"summary", "citations", "metrics", "why_explanation", "grounding_score"}
    assert expected.issubset(schema["properties"].keys())
