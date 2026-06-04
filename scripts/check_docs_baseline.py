"""check_docs_baseline.py — docs/demo baseline drift check for v0.1.

Delegates to check_repo_baseline for all deterministic release-critical checks.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "scripts" / "check_repo_baseline.py"
sys.exit(subprocess.call([sys.executable, str(CHECKER)]))
