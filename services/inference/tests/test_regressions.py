"""Regression tests for defects found after the P3-01 service landed.

Reference: https://github.com/KD4R/SatQuery/pull/17
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from services.inference.registry import ModelRegistry, ModelUnavailable

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Every place this repository reads a checkpoint. Adding a new one without
#: adding it here is the failure mode this list exists to make loud.
CHECKPOINT_READERS = (
    "services/inference/registry.py",
    "ml/scripts/generate_report.py",
    "ml/scripts/train_unet.py",
)


class _Arbitrary:
    """A class the restricted unpickler has no reason to trust."""

    def __init__(self, marker: str) -> None:
        self.marker = marker


@pytest.mark.parametrize("relative", CHECKPOINT_READERS)
def test_no_checkpoint_is_ever_read_with_an_unrestricted_unpickler(relative: str) -> None:
    """``weights_only=False`` was how all four load sites shipped, and CI caught it.

    A source assertion rather than a behavioural one, deliberately. The property
    being defended is *that the flag is set*, and the flag is one keystroke from
    being flipped back by someone chasing an unpickling error -- which is exactly
    what the error looks like it is asking for. This test runs in the lint job's
    environment, where torch is not installed and the behavioural test below
    cannot run, so it is the copy that guards the pull request.
    """
    source = (REPO_ROOT / relative).read_text()

    assert "weights_only=False" not in source, (
        f"{relative} reads a checkpoint with an unrestricted unpickler. A "
        "checkpoint is a pickle: loading one unrestricted executes whatever is "
        "inside it (CWE-502, bandit B614). Everything this repository stores in a "
        "checkpoint is tensors, dicts and floats, so weights_only=True costs "
        "nothing -- if a load now fails, the fix is to store plain data, not to "
        "reopen the code-execution path."
    )

    loads = re.findall(r"torch\.load\((?:[^()]|\([^()]*\))*\)", source, flags=re.DOTALL)
    assert loads, f"{relative} is listed as a checkpoint reader but calls no torch.load"
    for call in loads:
        assert "weights_only=True" in call, f"{relative}: {call} does not set weights_only"


def test_a_checkpoint_carrying_an_arbitrary_object_is_refused_not_executed() -> None:
    """The behavioural half: prove the restricted unpickler is actually in force.

    An attacker who can write into the models directory would be writing a pickle
    that the inference service loads -- the one process holding a token. Under
    ``weights_only=True`` reconstructing an unknown class is refused, and the
    registry turns that refusal into ``ModelUnavailable``, so the service degrades
    to the deterministic baseline instead of running the payload.
    """
    torch = pytest.importorskip("torch", reason="behavioural half needs requirements-ml.txt")

    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "hostile").mkdir()
        torch.save(
            {
                "state_dict": {},
                "architecture": {"in_channels": 2, "base_channels": 8, "depth": 2},
                "normalisation": _Arbitrary("payload"),
            },
            root / "hostile" / "best.pt",
        )
        (root / "hostile" / "metrics.json").write_text('{"epochs": 1, "seed": 0}')

        with pytest.raises(ModelUnavailable):
            ModelRegistry(root).load("hostile")
