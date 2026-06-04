"""v0.1.0 release acceptance tests."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_release_smoke_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release_v010.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"check_release_v010.py failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_release_acceptance_doc_exists() -> None:
    doc = ROOT / "docs" / "release" / "v0.1.0-acceptance.md"
    assert doc.exists(), "docs/release/v0.1.0-acceptance.md not found"
    content = doc.read_text(encoding="utf-8")
    assert "release-candidate" in content
    assert "0.1.0" in content
    assert "does not introduce automatic evidence-only review mode" in content


def test_evidence_only_contract_boundary_is_explicit() -> None:
    boundary = (
        "does not introduce an automatic evidence-only review mode, "
        "does not bypass governance decisions, "
        "and does not change runtime acceptance rules"
    )
    contract = ROOT / "docs" / "contracts" / "phase1-evidence-only-contract.md"
    readiness = ROOT / "docs" / "strategy" / "phase1-readiness.md"
    found = False
    for doc in (contract, readiness):
        if doc.exists() and boundary in doc.read_text(encoding="utf-8"):
            found = True
            break
    assert found, "Explicit boundary sentence not found in phase1 contract or readiness docs"
