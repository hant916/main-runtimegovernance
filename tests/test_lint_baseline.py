"""Baseline guard: `ruff check .` must pass for the whole repository.

README and docs/release/v0.1.0-acceptance.md list `ruff check .` as a validation
command. This test pins that baseline so lint drift in examples/ or scripts/ is caught
in CI, not just in src/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_ruff_check_clean() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "."],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"ruff check . failed:\n{result.stdout}\n{result.stderr}"
    )
