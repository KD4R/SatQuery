#!/usr/bin/env python3
"""Stamp the current code fingerprint into reports/evaluation.md in-place.

    PYTHONPATH="$PWD" python ml/scripts/stamp_report.py

WHEN TO USE THIS
----------------
Run this when the fingerprint is stale due to a change that genuinely cannot
move a reported number: a docstring, a type annotation, an import order fix.
It replaces the fingerprint line in reports/evaluation.md and nothing else;
the benchmark numbers, the dataset fingerprint, and the generation timestamp
are left exactly as the last generate_report.py run wrote them.

Do NOT use this after changing Otsu thresholds, the loss function, the
postprocessing rules, or any other logic that can alter a metric.  In those
cases regenerate properly:

    python3 fetch_sen1floods11.py --split all --count 400
    PYTHONPATH="$PWD" python ml/scripts/generate_report.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from ml.scripts.generate_report import code_fingerprint

REPORT = Path("reports/evaluation.md")
FINGERPRINT_ROW = re.compile(r"^(\|\s*code fingerprint\s*\|\s*)`([0-9a-f]+)`(\s*\|)", re.M)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    report_path = repo_root / REPORT

    if not report_path.is_file():
        print(
            f"{REPORT} does not exist -- run generate_report.py first.",
            file=sys.stderr,
        )
        return 1

    current = code_fingerprint(repo_root)
    text = report_path.read_text()

    match = FINGERPRINT_ROW.search(text)
    if match is None:
        print(
            f"{REPORT} has no fingerprint row -- it may have been hand-edited. "
            "Regenerate it instead of stamping.",
            file=sys.stderr,
        )
        return 1

    recorded = match.group(2)
    if recorded == current:
        print(f"{REPORT} is already current ({current}). Nothing to do.")
        return 0

    new_text = FINGERPRINT_ROW.sub(lambda m: f"{m.group(1)}`{current}`{m.group(3)}", text)
    report_path.write_text(new_text)
    print(f"Stamped {REPORT}: {recorded} -> {current}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
