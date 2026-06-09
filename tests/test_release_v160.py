"""v1.6 release hardening tests -- focused, deterministic, fixture-based."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def _add_src_path() -> None:
    sys.path.insert(0, str(ROOT / "src"))


# ---------------------------------------------------------------------------
# Smoke: check_release_v160.py passes
# ---------------------------------------------------------------------------


def test_release_smoke_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release_v160.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, (
        f"check_release_v160.py failed (exit {result.returncode}):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# v1.5 closure
# ---------------------------------------------------------------------------


def test_v150_checker_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release_v150.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, f"v1.5 checker failed: {result.stderr}"


def test_v150_key_source_files_exist() -> None:
    for path in (
        "src/ailuros/adapters/evidence_package/loader.py",
        "src/ailuros/adapters/evidence_package/validator.py",
        "src/ailuros/adapters/evidence_package/audit.py",
        "src/ailuros/adapters/evidence_package/markdown_report.py",
    ):
        p = ROOT / path
        assert p.exists(), f"{path} missing"


# ---------------------------------------------------------------------------
# Golden fixture validation
# ---------------------------------------------------------------------------


def test_v160_golden_fixtures_exist() -> None:
    v160 = ROOT / "fixtures" / "ailuros" / "v160"
    assert v160.is_dir(), "fixtures/ailuros/v160/ missing"
    for outcome in ("pass-governance-run", "warn-anomaly-run", "fail-contract-run"):
        pkg = v160 / outcome
        assert pkg.is_dir(), f"{outcome} fixture dir missing"
        assert (pkg / "manifest.json").is_file(), f"{outcome}/manifest.json missing"
        assert (pkg / "timeline.json").is_file(), f"{outcome}/timeline.json missing"


def test_v160_golden_fixture_importable_and_consistent() -> None:
    from ailuros.adapters.evidence_package import audit_evidence_package
    from ailuros.core.audit import AuditDecision

    V160 = ROOT / "fixtures" / "ailuros" / "v160"

    pass_result = audit_evidence_package(V160 / "pass-governance-run")
    assert pass_result.decision == AuditDecision.PASS

    warn_result = audit_evidence_package(V160 / "warn-anomaly-run")
    assert warn_result.decision == AuditDecision.WARN

    fail_result = audit_evidence_package(V160 / "fail-contract-run")
    assert fail_result.decision == AuditDecision.FAIL

    decisions = {pass_result.decision, warn_result.decision, fail_result.decision}
    assert decisions == {AuditDecision.PASS, AuditDecision.WARN, AuditDecision.FAIL}


def test_v160_golden_fixture_tests_pass() -> None:
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_v160_golden_audit_fixtures.py", "-q", "--no-header",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0, (
        f"golden fixture tests failed (exit {result.returncode}):\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Report-quality regression
# ---------------------------------------------------------------------------


def test_v160_report_quality_tests_pass() -> None:
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_v160_audit_report_quality.py", "-q", "--no-header",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0, (
        f"report quality tests failed (exit {result.returncode}):\n{result.stderr}"
    )


def test_v160_report_quality_tests_cover_sections() -> None:
    qual = ROOT / "tests" / "test_v160_audit_report_quality.py"
    content = qual.read_text(encoding="utf-8")
    sections = (
        "## Decision", "## Summary", "## Checks",
        "## Warnings", "## Errors", "## Verdict",
    )
    for section in sections:
        assert section in content, (
            f"Required section {section!r} not in report quality tests"
        )


def test_v160_report_quality_tests_cover_determinism() -> None:
    qual = ROOT / "tests" / "test_v160_audit_report_quality.py"
    content = qual.read_text(encoding="utf-8")
    assert "test_report_output_is_deterministic" in content
    assert "test_three_fixtures_produce_distinct_reports" in content


# ---------------------------------------------------------------------------
# Docs boundary
# ---------------------------------------------------------------------------


def test_readme_mentions_release_status() -> None:
    readme = ROOT / "README.md"
    content = readme.read_text(encoding="utf-8")
    assert "v1.5" in content, "README missing v1.5 mention"


def test_roadmap_has_v15_v20_boundary() -> None:
    roadmap = ROOT / "docs" / "strategy" / "roadmap.md"
    content = roadmap.read_text(encoding="utf-8")
    assert "v1.5" in content, "roadmap missing v1.5"
    assert "v2.0" in content, "roadmap missing v2.0 boundary"


# ---------------------------------------------------------------------------
# Non-goals preserved
# ---------------------------------------------------------------------------


def test_non_goals_http_absent_from_evidence_package_init() -> None:
    init_path = ROOT / "src" / "ailuros" / "adapters" / "evidence_package" / "__init__.py"
    content = init_path.read_text(encoding="utf-8").lower()
    assert "http" not in content, "HTTP reference found in evidence_package __init__"


def test_non_goals_server_block_absent_from_evidence_package_init() -> None:
    init_path = ROOT / "src" / "ailuros" / "adapters" / "evidence_package" / "__init__.py"
    content = init_path.read_text(encoding="utf-8").lower()
    assert "server" not in content, "server reference found in evidence_package __init__"
    assert "block" not in content, "block reference found in evidence_package __init__"
