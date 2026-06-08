from __future__ import annotations

from pathlib import Path

from ailuros.adapters.evidence_package import (
    audit_evidence_package,
    audit_result_to_markdown,
    validate_evidence_package_contract,
)
from ailuros.core.audit import AuditDecision, AuditResult
from ailuros.core.validation import ValidationResult

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V160 = ROOT / "fixtures" / "ailuros" / "v160"

PASS_PKG = V160 / "pass-governance-run"
WARN_PKG = V160 / "warn-anomaly-run"
FAIL_PKG = V160 / "fail-contract-run"

# ---------------------------------------------------------------------------
# Fixture existence
# ---------------------------------------------------------------------------


def test_fixture_dirs_exist():
    for pkg in (PASS_PKG, WARN_PKG, FAIL_PKG):
        assert pkg.is_dir(), f"missing fixture directory: {pkg}"
        assert (pkg / "manifest.json").is_file(), f"missing manifest: {pkg}"
        assert (pkg / "timeline.json").is_file(), f"missing timeline: {pkg}"


# ---------------------------------------------------------------------------
# pass-governance-run (accept → pass)
# ---------------------------------------------------------------------------


def test_pass_validation():
    result = validate_evidence_package_contract(PASS_PKG)
    assert isinstance(result, ValidationResult)
    assert result.ok is True
    assert result.errors == []
    assert result.warnings == []
    assert result.source == "v160-agent"
    assert result.schema_version == "ailuros.timeline.v0"
    assert result.run_id == "run-v160-pass-001"
    assert result.events_count == 3


def test_pass_audit_decision():
    result = audit_evidence_package(PASS_PKG)
    assert isinstance(result, AuditResult)
    assert result.ok is True
    assert result.decision == AuditDecision.PASS
    assert result.governance_mode == "observe"
    assert result.source == "v160-agent"
    assert result.run_id == "run-v160-pass-001"
    assert result.events_count == 3
    assert result.rules_evaluated == 2
    assert result.errors == []
    assert result.warnings == []


def test_pass_report_deterministic():
    first = audit_result_to_markdown(audit_evidence_package(PASS_PKG))
    second = audit_result_to_markdown(audit_evidence_package(PASS_PKG))
    assert first == second
    assert "**PASS**" in first
    assert "Evidence is clean and contract-valid." in first


# ---------------------------------------------------------------------------
# warn-anomaly-run (require_review → warn)
# ---------------------------------------------------------------------------


def test_warn_validation():
    result = validate_evidence_package_contract(WARN_PKG)
    assert isinstance(result, ValidationResult)
    assert result.ok is True
    assert result.errors == []
    assert len(result.warnings) >= 1
    assert any("unknown event_type" in w for w in result.warnings)
    assert result.source == "v160-agent"
    assert result.run_id == "run-v160-warn-001"
    assert result.events_count == 3


def test_warn_audit_decision():
    result = audit_evidence_package(WARN_PKG)
    assert isinstance(result, AuditResult)
    assert result.ok is True
    assert result.decision == AuditDecision.WARN
    assert result.governance_mode == "guard"
    assert result.source == "v160-agent"
    assert result.run_id == "run-v160-warn-001"
    assert result.events_count == 3
    assert result.rules_evaluated == 2
    assert result.errors == []
    assert len(result.warnings) >= 1


def test_warn_report_contains_anomaly_signal():
    md = audit_result_to_markdown(audit_evidence_package(WARN_PKG))
    assert "**WARN**" in md
    assert "custom_governance_review" in md
    assert "Evidence is valid but has tolerated anomalies." in md


# ---------------------------------------------------------------------------
# fail-contract-run (block → fail)
# ---------------------------------------------------------------------------


def test_fail_validation():
    result = validate_evidence_package_contract(FAIL_PKG)
    assert isinstance(result, ValidationResult)
    assert result.ok is False
    assert len(result.errors) >= 1
    assert any("must not be empty" in e for e in result.errors)
    assert result.source == "v160-agent"
    assert result.run_id == "run-v160-fail-001"
    assert result.events_count == 0


def test_fail_audit_decision():
    result = audit_evidence_package(FAIL_PKG)
    assert isinstance(result, AuditResult)
    assert result.ok is False
    assert result.decision == AuditDecision.FAIL
    assert result.governance_mode == "block"
    assert result.source == "v160-agent"
    assert result.run_id == "run-v160-fail-001"
    assert result.events_count == 0
    assert result.rules_evaluated == 2
    assert len(result.errors) >= 1
    assert result.warnings == []


def test_fail_report_contains_contract_violation():
    md = audit_result_to_markdown(audit_evidence_package(FAIL_PKG))
    assert "**FAIL**" in md
    assert "must not be empty" in md
    assert "Evidence violates the package contract." in md


# ---------------------------------------------------------------------------
# Cross-fixture: deterministic outcomes are stable
# ---------------------------------------------------------------------------


def test_all_outcomes_distinct():
    decisions = {
        audit_evidence_package(PASS_PKG).decision,
        audit_evidence_package(WARN_PKG).decision,
        audit_evidence_package(FAIL_PKG).decision,
    }
    assert decisions == {AuditDecision.PASS, AuditDecision.WARN, AuditDecision.FAIL}
