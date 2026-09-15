"""The P3-15 staleness gate, and the bypass that once disabled it.

Why this file is worth its length: the gate is the only thing standing between a
committed accuracy figure and the code that stopped producing it, and it has
already been defeated once -- not by a subtle bug, but by a CI step that ran
immediately before it and made its comparison unconditional. Nothing failed. CI
went green. The report kept publishing IoU 0.259 for code that no longer computed
it.

So these tests assert two different kinds of thing. Most check the gate's logic.
The last one checks the *workflow file*, because the defect was never in the
Python -- ``check_report_fresh.py`` was correct throughout, and was simply handed a
report that had been rewritten a second earlier.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ml.scripts.report_freshness import (
    CALIBRATION_REPORT,
    REPORT,
    REPORTS,
    WAIVERS,
    changed_modules,
    code_fingerprint,
    read_recorded_fingerprint,
    read_waivers,
    write_sidecar,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"


def run_gate(cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the gate as CI runs it: a subprocess, against a repo tree."""
    return subprocess.run(
        [sys.executable, str(cwd / "ml/scripts/check_report_fresh.py")],
        cwd=cwd,
        env={"PYTHONPATH": str(cwd), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal tree with the real gate, the real modules, and a current report."""
    for relative in (
        "ml/scripts/check_report_fresh.py",
        "ml/scripts/report_freshness.py",
        "ml/scripts/__init__.py",
        "ml/__init__.py",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((REPO_ROOT / relative).read_bytes())

    from ml.scripts.report_freshness import REPORTS

    for modules in REPORTS.values():
        for relative in modules:
            destination = tmp_path / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((REPO_ROOT / relative).read_bytes())

    (tmp_path / "reports").mkdir()
    # Every report the gate walks, each stamped with its own module list's
    # fingerprint. Writing only one of them would make the fixture pass for a
    # reason the real repository does not enjoy.
    for report, modules in REPORTS.items():
        (tmp_path / report).write_text(
            f"# {report.stem}\n\n"
            "| field | value |\n| --- | --- |\n"
            f"| code fingerprint | `{code_fingerprint(tmp_path, modules)}` |\n\n"
            "| method | IoU |\n| --- | --- |\n| U-Net | 0.259 |\n"
        )
    write_sidecar(tmp_path)
    return tmp_path


def test_the_gate_passes_when_the_report_matches_the_code(repo: Path) -> None:
    result = run_gate(repo)
    assert result.returncode == 0, result.stderr
    assert "is current" in result.stdout


def test_inverting_the_water_polarity_fails_the_gate(repo: Path) -> None:
    """The scenario the gate exists for, and the one the bypass let through.

    ``np.less`` selects water because water is dark in SAR. Swapping it for
    ``np.greater`` turns every water measurement into a measurement of everything
    that is not water -- the largest possible error this pipeline can make, and one
    that raises nothing and changes no shape. The only signal is that the committed
    numbers stop describing the code.
    """
    baseline = repo / "ml/pipeline/baseline.py"
    source = baseline.read_text()
    assert "np.less(decibels, threshold_db" in source
    baseline.write_text(
        source.replace("np.less(decibels, threshold_db", "np.greater(decibels, threshold_db")
    )

    result = run_gate(repo)

    assert result.returncode == 1
    assert "is stale" in result.stderr
    assert "ml/pipeline/baseline.py" in result.stderr, (
        "the failure must name the module that moved; 'something changed' is what "
        "sent someone looking for a bypass in the first place"
    )


def test_a_waiver_lets_a_change_through_and_says_so_loudly(repo: Path) -> None:
    (repo / "ml/geo/area.py").write_text(
        (repo / "ml/geo/area.py").read_text() + "\n# a comment that cannot move a number\n"
    )
    changed_fingerprint = code_fingerprint(repo)

    (repo / WAIVERS).write_text(
        "| fingerprint | modules changed | waived by | date | reason |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"| `{changed_fingerprint}` | `ml/geo/area.py` | A Person | 2026-09-13 | comment only |\n"
    )

    result = run_gate(repo)

    assert result.returncode == 0, result.stderr
    assert "WAIVED" in result.stdout
    assert "A Person" in result.stdout
    assert "comment only" in result.stdout


def test_a_waiver_for_a_different_fingerprint_does_not_help(repo: Path) -> None:
    """Waivers are per-fingerprint, so they expire the moment anything else moves.

    Without this the mechanism would degrade into the bypass it replaced: one
    waiver filed for a docstring, and every later change riding in behind it.
    """
    (repo / "ml/geo/area.py").write_text((repo / "ml/geo/area.py").read_text() + "\n# one\n")
    first = code_fingerprint(repo)
    (repo / WAIVERS).write_text(
        "| fingerprint | modules changed | waived by | date | reason |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"| `{first}` | `ml/geo/area.py` | A Person | 2026-09-13 | comment only |\n"
    )

    (repo / "ml/pipeline/baseline.py").write_text(
        (repo / "ml/pipeline/baseline.py").read_text().replace("np.less(", "np.greater(", 1)
    )

    result = run_gate(repo)
    assert result.returncode == 1
    assert "is stale" in result.stderr


def test_an_unparseable_waiver_file_fails_closed(repo: Path) -> None:
    (repo / "ml/geo/area.py").write_text((repo / "ml/geo/area.py").read_text() + "\n# x\n")
    (repo / WAIVERS).write_text("this file is not a table at all\n")

    result = run_gate(repo)
    assert result.returncode == 1


def test_a_missing_fingerprint_row_is_a_failure_not_a_pass(repo: Path) -> None:
    (repo / REPORT).write_text("# Evaluation\n\nsomebody hand-edited this\n")
    result = run_gate(repo)
    assert result.returncode == 1
    assert "no code fingerprint" in result.stderr


def test_read_waivers_is_empty_when_the_file_is_absent(repo: Path) -> None:
    assert read_waivers(repo) == {}


def test_changed_modules_says_nothing_rather_than_nothing_changed(tmp_path: Path) -> None:
    """No sidecar must not read as "no modules changed"."""
    assert changed_modules(tmp_path) == ()


def test_the_recorded_fingerprint_round_trips(repo: Path) -> None:
    assert read_recorded_fingerprint(repo) == code_fingerprint(repo)


def test_nothing_runs_before_the_gate_in_ci() -> None:
    """The actual defect was here, not in any Python file.

    ``stamp_report.py`` rewrote the recorded fingerprint to match the current code
    and CI ran it first, so the comparison compared a value against itself. The
    Python was never wrong. This asserts on the workflow because that is where the
    bypass lived and where it would come back.
    """
    workflow = WORKFLOW.read_text()

    step = workflow.split("Evaluation report is not stale (P3-15)", 1)
    assert len(step) == 2, "the P3-15 step is missing from ci.yml"
    body = step[1].split("- name:", 1)[0]

    commands = [
        line.strip()
        for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#") and "python" in line
    ]
    assert commands == ['run: PYTHONPATH="$PWD" python ml/scripts/check_report_fresh.py'], (
        "the P3-15 step must run the gate and nothing else. Anything running before "
        "it can rewrite the report it is about to check, which is exactly how this "
        f"gate was disabled once already. Found: {commands}"
    )

    assert "stamp_report" not in workflow, (
        "stamp_report.py stamped the current fingerprint unconditionally; it was "
        "replaced by waive_report.py, which requires a name and a reason and never "
        "runs in CI"
    )


# --------------------------------------------------------------------------- #
# The report is measured against hand labels, and only hand labels             #
# --------------------------------------------------------------------------- #


def test_the_report_generator_filters_to_hand_labels() -> None:
    """A source assertion, because the behavioural version needs 400 chips and torch.

    This nearly went wrong for real. `discover_chips` gained weakly-labelled chips
    so they could be trained on; `generate_report.py` scored everything it
    returned; and the next regeneration -- run while the weak fetch was still
    downloading -- silently grew from 400 chips to 859 and added two whole regions
    of Otsu-scored rows to the per-region table. Nothing raised. The column header
    still said IoU. The numbers had simply stopped being a measurement of the model
    and started being a measurement of how well it imitates Otsu.

    Caught only because the regeneration was diffed against the previous report.
    That is too thin a thread for the property to hang on.
    """
    source = (REPO_ROOT / "ml/scripts/generate_report.py").read_text()

    assert "Labelling.HAND" in source, (
        "generate_report.py must filter discovered chips to hand labels. Without "
        "it, every weakly-labelled chip on disk enters the reported accuracy "
        "figures scored against automatically derived labels, in the same columns "
        "as the ground-truth ones."
    )

    discovery = source.index("discover_chips(args.root)")
    filtering = source.index("c.labelling is Labelling.HAND")
    split = source.index("split_by_region(chips)")
    assert discovery < filtering < split, (
        "the filter must sit between discovery and the split: after discovery "
        "so there is something to filter, and before the split so held-out "
        "regions are not computed over chips the report then refuses to score"
    )


def test_the_calibration_report_is_gated_too(repo: Path) -> None:
    """Both committed reports, each against its own module list.

    A calibration report rots exactly the way an evaluation report does -- someone
    changes the temperature search, the committed ECE quietly stops describing the
    code, and nothing says so. The lists are separate on purpose: a change to Otsu
    cannot move an ECE and a change to the temperature search cannot move an IoU,
    so one shared list would fire each report on the other's edits, and a gate that
    fires for reasons the reader cannot act on is one that gets bypassed (D16).
    """
    assert CALIBRATION_REPORT in REPORTS
    assert REPORTS[CALIBRATION_REPORT] != REPORTS[REPORT]

    calibration = repo / "ml/evaluation/calibration.py"
    calibration.write_text(
        calibration.read_text().replace("DEFAULT_BINS = 10", "DEFAULT_BINS = 20")
    )

    result = run_gate(repo)

    assert result.returncode == 1
    assert "calibration.md is stale" in result.stderr
    assert "ml/evaluation/calibration.py" in result.stderr
    # The evaluation report must be untouched by a calibration-only change.
    assert "evaluation.md is current" in result.stdout


def test_a_missing_committed_report_fails_rather_than_skips(repo: Path) -> None:
    """Fail closed. A gate that skips when its input is absent reports green while
    checking nothing, which is worse than no gate because people trust it."""
    (repo / CALIBRATION_REPORT).unlink()
    result = run_gate(repo)
    assert result.returncode == 1
    assert "calibration.md is missing" in result.stderr
