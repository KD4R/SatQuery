"""Scoring several models in one report, and why it has to be one process.

Two models compared from separate runs are two numbers measured on whatever each
run happened to see. ADR-0007 D15 is the record of that going wrong here: the
deterministic baseline appeared to fall from 0.242 to 0.189 between two reports
while its code was byte-identical, because the validation set had grown.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ml.scripts.generate_report import _best, _headline, discover_models

pytestmark = pytest.mark.unit


def counts(tp: int, fp: int, fn: int, tn: int) -> dict[str, int]:
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "ignored_pixels": 0,
    }


def row(**models: tuple[int, int, int, int]):
    record: dict = {"baseline_counts": counts(10, 10, 10, 970), "baseline_iou": 0.33}
    record["baseline_f1"] = 0.5
    for name, c in models.items():
        record[f"counts::{name}"] = counts(*c)
        record[f"iou::{name}"] = c[0] / (c[0] + c[1] + c[2])
        record[f"f1::{name}"] = 2 * c[0] / (2 * c[0] + c[1] + c[2])
    return record


def test_discovery_finds_every_checkpoint(tmp_path: Path) -> None:
    for name in ("flood-unet", "hand-only-v2", "pretrain"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "best.pt").write_bytes(b"x")
    (tmp_path / "half-finished").mkdir()  # no best.pt yet

    found = discover_models(tmp_path, None)

    assert set(found) == {"flood-unet", "hand-only-v2", "pretrain"}
    assert found["pretrain"] == tmp_path / "pretrain" / "best.pt"


def test_naming_one_model_scores_only_that_one(tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "best.pt").write_bytes(b"x")

    assert set(discover_models(tmp_path, tmp_path / "a" / "best.pt")) == {"a"}


def test_a_named_checkpoint_that_does_not_exist_yields_nothing(tmp_path: Path) -> None:
    """Not a crash and not a silent fallback to everything: asking for one model
    that is absent must not quietly score a different one."""
    assert discover_models(tmp_path, tmp_path / "ghost" / "best.pt") == {}


def test_an_empty_directory_is_a_baseline_only_report(tmp_path: Path) -> None:
    assert discover_models(tmp_path, None) == {}


def test_the_best_model_is_chosen_by_pooled_not_per_chip_iou() -> None:
    """The two aggregations can disagree about which model won, and pooled is the
    one the literature reports -- so the tables must follow pooled, or the report
    would rank by one number and tabulate by another.
    """
    rows = [
        # `wide` wins pooled: it finds far more of the water that exists.
        # `narrow` wins the per-chip mean by doing well on the tiny chip.
        row(wide=(9000, 1000, 1000, 89_000), narrow=(1, 0, 0, 98_999)),
        row(wide=(9000, 1000, 1000, 89_000), narrow=(0, 0, 9000, 91_000)),
    ]
    names = ("wide", "narrow")

    assert _best(rows, names) == "wide"


def test_the_headline_lists_every_model_and_bolds_the_winner() -> None:
    rows = [row(alpha=(100, 50, 50, 800), beta=(200, 10, 10, 780))]
    lines = "\n".join(_headline(rows, ("alpha", "beta")))

    assert "| alpha |" in lines
    assert "| beta |" in lines
    assert "**" in lines.split("| beta |")[1].split("\n")[0], "the winner is emphasised"
    assert "**" not in lines.split("| alpha |")[1].split("\n")[0]


def test_the_headline_survives_a_model_that_scored_nothing() -> None:
    """A checkpoint that failed to load is dropped from the comparison, not
    rendered as a row of zeros -- which would read as a model that found no water
    rather than one that never ran."""
    rows = [row(alpha=(100, 50, 50, 800))]
    rows[0]["counts::ghost"] = None

    lines = "\n".join(_headline(rows, ("alpha", "ghost")))

    assert "| alpha |" in lines
    assert "| ghost |" not in lines


def test_a_baseline_only_report_still_renders() -> None:
    lines = "\n".join(_headline([row()], ()))
    assert "deterministic baseline" in lines
