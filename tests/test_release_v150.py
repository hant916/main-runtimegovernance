"""v1.5 release closure tests — focused, deterministic, fixture-based."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def _add_src_path() -> None:
    sys.path.insert(0, str(ROOT / "src"))


def test_release_smoke_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release_v150.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, (
        f"check_release_v150.py failed (exit {result.returncode}):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_release_doc_exists_and_accepted() -> None:
    doc = ROOT / "docs" / "release" / "v1.5-post-run-governance.md"
    assert doc.exists(), "docs/release/v1.5-post-run-governance.md not found"
    content = doc.read_text(encoding="utf-8")
    assert "**Status:** Accepted" in content
    assert "v1.5" in content


def test_contract_doc_exists_and_accepted() -> None:
    doc = ROOT / "docs" / "contracts" / "evidence-package-post-run-governance-v15.md"
    assert doc.exists(), "contract doc not found"
    content = doc.read_text(encoding="utf-8")
    assert "**Status:** Accepted" in content


def test_five_pack_source_files_exist() -> None:
    packs = [
        # C-008: Clarify evidence handoff
        ("scripts/validate_clarify_handoff.py", "validate_clarify_timeline"),
        # A-005R1: Package loader
        ("src/ailuros/adapters/evidence_package/loader.py", "load_evidence_package"),
        # A-005R2: Timeline contract validator
        (
            "src/ailuros/adapters/evidence_package/validator.py",
            "validate_evidence_package_contract",
        ),
        # A-005R3: Minimal governance decision
        ("src/ailuros/adapters/evidence_package/audit.py", "audit_evidence_package"),
        # A-006R: Markdown audit report
        ("src/ailuros/adapters/evidence_package/markdown_report.py", "audit_result_to_markdown"),
    ]
    for path, symbol in packs:
        p = ROOT / path
        assert p.exists(), f"{path} missing"
        content = p.read_text(encoding="utf-8")
        assert symbol in content, f"{symbol} not found in {path}"


def test_public_api_exports_all_required_symbols() -> None:
    from ailuros.adapters.evidence_package import __all__ as public_names

    required = [
        "audit_evidence_package",
        "audit_result_to_dict",
        "audit_result_to_json",
        "audit_result_to_markdown",
        "load_evidence_package",
        "validate_evidence_package_contract",
    ]
    for name in required:
        assert name in public_names, f"{name!r} missing from __all__"


def test_fixture_exists() -> None:
    fixture_dir = ROOT / "tests" / "fixtures" / "evidence_package" / "valid-v15"
    assert fixture_dir.is_dir(), "valid-v15 fixture dir missing"
    assert (fixture_dir / "manifest.json").exists(), "manifest.json missing"
    assert (fixture_dir / "timeline.json").exists(), "timeline.json missing"


def test_roadmap_mentions_v15() -> None:
    roadmap = ROOT / "docs" / "strategy" / "roadmap.md"
    assert roadmap.exists()
    content = roadmap.read_text(encoding="utf-8")
    assert "v1.5" in content
    assert "C-008" in content
    assert "A-005R1" in content
    assert "A-005R2" in content
    assert "A-005R3" in content
    assert "A-006R" in content


def test_non_goals_preserved_in_evidence_package_init() -> None:
    init_path = ROOT / "src" / "ailuros" / "adapters" / "evidence_package" / "__init__.py"
    content = init_path.read_text(encoding="utf-8").lower()
    assert "http" not in content, "HTTP reference in evidence_package __init__"
    assert "block" not in content, "runtime block reference in evidence_package __init__"
    assert "server" not in content, "server reference in evidence_package __init__"
