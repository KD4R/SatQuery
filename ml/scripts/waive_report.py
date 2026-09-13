#!/usr/bin/env python3
"""Record a human waiver for a stale evaluation report (P3-15).

    PYTHONPATH="$PWD" python ml/scripts/waive_report.py \
        --by "Your Name" --reason "type annotation only; no arithmetic touched"

WHY THIS EXISTS
---------------
The staleness gate compares a hash of the analysis modules against the hash
recorded in ``reports/evaluation.md``. That is the right check, and it fires
correctly on changes that provably cannot move a number -- a docstring, a type
annotation, an operator swap that returns an identical value. Regenerating the
report costs a 533 MB download and a full re-score, which is an absurd price for
a comment fix, and a gate whose only escape is absurd is a gate that gets
bypassed. It was, once: an earlier revision of this script stamped the current
fingerprint into the report and CI ran it *before* the check, which meant the
check could no longer fail at all. Inverting the water polarity in
``ml/pipeline/baseline.py`` passed green while the report still published
IoU 0.259.

So the escape hatch stays, with the two properties the bypass lacked: a person's
name is on it, and it shows up in the diff.

WHAT IT WILL NOT DO
-------------------
It will not run in CI. It writes to a committed file, so a waiver reaches main
only through a pull request a reviewer reads -- and the row names the modules that
changed, so "ml/pipeline/baseline.py" sitting next to "docstring only" is visible
at a glance rather than buried in a hash.

If a number could have moved, this is the wrong tool. Regenerate:

    python3 fetch_sen1floods11.py --split all --count 400
    PYTHONPATH="$PWD" python ml/scripts/generate_report.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from ml.scripts.report_freshness import (
    WAIVERS,
    changed_modules,
    code_fingerprint,
    read_recorded_fingerprint,
    read_waivers,
)

HEADER = """# Evaluation report waivers

Each row says: the analysis modules changed, and a named person asserts the change
could not move a number in `reports/evaluation.md`. The gate in
`ml/scripts/check_report_fresh.py` accepts a fingerprint listed here.

A row is a claim under review, not a formality. If the modules column names
something that does arithmetic, the reviewer should ask for a regeneration.

| fingerprint | modules changed | waived by | date | reason |
| --- | --- | --- | --- | --- |
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--by", required=True, help="who is making this assertion")
    parser.add_argument(
        "--reason",
        required=True,
        help="why the change cannot move a number, specifically",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]

    recorded = read_recorded_fingerprint(repo_root)
    if recorded is None:
        print(
            "reports/evaluation.md is missing or carries no fingerprint. "
            "There is nothing to waive -- generate the report first.",
            file=sys.stderr,
        )
        return 1

    current = code_fingerprint(repo_root)
    if current == recorded:
        print(f"The report is already current ({current}). Nothing to waive.")
        return 0

    if current in read_waivers(repo_root):
        print(f"Fingerprint {current} is already waived.")
        return 0

    changed = changed_modules(repo_root)
    modules = "<br>".join(f"`{m}`" for m in changed) if changed else "_unknown_"

    reason = args.reason.strip().replace("|", "\\|")
    by = args.by.strip().replace("|", "\\|")
    if not reason or not by:
        print("--by and --reason must not be empty.", file=sys.stderr)
        return 1

    path = repo_root / WAIVERS
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(HEADER)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"| `{current}` | {modules} | {by} | {date.today().isoformat()} | {reason} |\n"
        )

    print(f"Waived {current} (was {recorded}).")
    print(f"Modules changed: {', '.join(changed) if changed else 'unknown'}")
    print(f"Commit {WAIVERS} with your change so a reviewer sees the claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
