#!/usr/bin/env python3
"""Install the shared git hooks from scripts/hooks/ into .git/hooks/.

    python scripts/install_hooks.py

Idempotent: safe to run more than once.
"""
import shutil
import stat
from pathlib import Path

HOOKS_SRC = Path(__file__).parent / "hooks"
HOOKS_DST = Path(__file__).parents[1] / ".git" / "hooks"

for src in HOOKS_SRC.iterdir():
    if src.is_file():
        dst = HOOKS_DST / src.name
        shutil.copy2(src, dst)
        dst.chmod(dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print(f"installed: {dst}")

print("Done.")
