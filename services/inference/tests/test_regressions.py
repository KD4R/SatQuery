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


# --------------------------------------------------------------------------- #
# Model cards: unmeasured is not the same as measured-and-failed               #
# --------------------------------------------------------------------------- #

import json  # noqa: E402


def register(root: Path, name: str, metrics: dict | None = None, calibration: dict | None = None):
    (root / name).mkdir(parents=True)
    (root / name / "best.pt").write_bytes(b"not a real checkpoint")
    if metrics is not None:
        (root / name / "metrics.json").write_text(json.dumps(metrics))
    if calibration is not None:
        (root / name / "calibration.json").write_text(json.dumps(calibration))


def test_calibration_facts_reach_the_card(tmp_path: Path) -> None:
    register(
        tmp_path,
        "m",
        metrics={"epochs": 1, "seed": 0},
        calibration={"ece_calibrated": 0.126, "passes_bar": False, "report": "reports/c.md"},
    )
    (card,) = ModelRegistry(tmp_path).cards()

    assert card.calibration_ece == 0.126
    assert card.calibration_passes is False
    assert card.calibration_report == "reports/c.md"


def test_an_uncalibrated_model_reports_none_not_false(tmp_path: Path) -> None:
    """ "Nobody has measured this" and "measured, and it failed the bar" are
    different claims. Defaulting to False would let an unexamined model be
    described as a failed one -- the same trap `beats_baseline` avoids."""
    register(tmp_path, "m", metrics={"epochs": 1, "seed": 0})
    (card,) = ModelRegistry(tmp_path).cards()

    assert card.calibration_passes is None
    assert card.calibration_ece is None


def test_an_unreadable_calibration_file_does_not_take_the_model_down(tmp_path: Path) -> None:
    """A model that cannot be listed cannot be served, and a corrupt sidecar is a
    reason to know less about a model, not to lose it."""
    register(tmp_path, "m", metrics={"epochs": 1, "seed": 0})
    (tmp_path / "m" / "calibration.json").write_text("{ not json")

    (card,) = ModelRegistry(tmp_path).cards()
    assert card.name == "m"
    assert card.calibration_passes is None


def test_provenance_absent_from_an_older_metrics_file_reads_as_unknown(tmp_path: Path) -> None:
    """Checkpoints trained before these fields existed must still register.

    A long training run holds its copy of the script in memory, so a run already
    in flight when this landed writes the old format. Refusing it would discard a
    three-hour result over missing metadata.
    """
    register(tmp_path, "m", metrics={"epochs": 20, "seed": 0, "parameters": 486553})
    (card,) = ModelRegistry(tmp_path).cards()

    assert card.in_channels is None
    assert card.uses_permanent_water_prior is None
    assert card.training_labelling is None
    assert card.version == "e20-s0"


def test_provenance_reaches_the_card_when_recorded(tmp_path: Path) -> None:
    register(
        tmp_path,
        "m",
        metrics={
            "epochs": 30,
            "seed": 0,
            "in_channels": 3,
            "uses_permanent_water_prior": True,
            "training_labelling": "hand",
            "model": {"iou": 0.42},
            "baseline": {"iou": 0.20},
        },
    )
    (card,) = ModelRegistry(tmp_path).cards()

    assert (card.in_channels, card.uses_permanent_water_prior) == (3, True)
    assert card.training_labelling == "hand"
    assert card.beats_baseline is True
    assert card.to_dict()["in_channels"] == 3
