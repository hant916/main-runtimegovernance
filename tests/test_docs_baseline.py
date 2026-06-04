"""Tests for the docs/demo baseline drift checker."""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CHECKER = SCRIPTS / "check_docs_baseline.py"


def test_checker_runs_with_exit_zero():
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    assert result.returncode == 0
