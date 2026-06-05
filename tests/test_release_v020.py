"""v0.2.0 release acceptance tests."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_release_smoke_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release_v020.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"check_release_v020.py failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_release_acceptance_doc_exists() -> None:
    doc = ROOT / "docs" / "release" / "v0.2.0-acceptance.md"
    assert doc.exists(), "docs/release/v0.2.0-acceptance.md not found"
    content = doc.read_text(encoding="utf-8")
    assert "acceptance-defined" in content
    assert "evidence-only" in content
    assert "HTTP write API" in content
    assert "Non-goals" in content
    assert "Acceptance Matrix" in content
    assert "IMPLEMENTED" in content
    assert "NON-GOAL" in content
    assert "Pipeline boundary" in content
    assert "Audit package" in content
    assert "Evidence demo" in content


def test_evidence_only_contract_boundary_is_explicit() -> None:
    boundary = (
        "does not introduce an automatic evidence-only review mode, "
        "does not bypass governance decisions, "
        "and does not change runtime acceptance rules"
    )
    contract = ROOT / "docs" / "contracts" / "phase1-evidence-only-contract.md"
    readiness = ROOT / "docs" / "strategy" / "phase1-readiness.md"
    acceptance = ROOT / "docs" / "release" / "v0.2.0-acceptance.md"
    found = False
    for doc in (contract, readiness, acceptance):
        if doc.exists() and boundary in doc.read_text(encoding="utf-8"):
            found = True
            break
    assert found, (
        "Explicit boundary sentence not found in phase1 contract, "
        "readiness, or v0.2 acceptance docs"
    )


def test_v020_acceptance_non_goals_cover_server_write_api() -> None:
    doc = ROOT / "docs" / "release" / "v0.2.0-acceptance.md"
    content = doc.read_text(encoding="utf-8")
    assert "does not introduce an HTTP write API" in content
    assert "do_POST" in content
    assert "does not claim server write API support" in content


def test_v020_acceptance_non_goals_cover_clarify_in_core() -> None:
    doc = ROOT / "docs" / "release" / "v0.2.0-acceptance.md"
    content = doc.read_text(encoding="utf-8")
    assert "does not claim real Clarify integration inside core" in content


def test_evidence_module_is_importable() -> None:
    from ailuros.evidence import EvidenceRecord, export_evidence, ingest_evidence

    assert EvidenceRecord is not None
    assert callable(export_evidence)
    assert callable(ingest_evidence)


def test_evidence_model_fields() -> None:
    from ailuros.evidence import EvidenceRecord

    fields = EvidenceRecord.model_fields
    assert "version" in fields
    assert "run_id" in fields
    assert "event_type" in fields
    assert "payload" in fields
    assert "timestamp" in fields
