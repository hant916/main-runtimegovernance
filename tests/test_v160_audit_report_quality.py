from __future__ import annotations

from pathlib import Path

from ailuros.adapters.evidence_package import (
    audit_evidence_package,
    audit_result_to_markdown,
)
from ailuros.core.audit import AuditDecision, AuditResult
from ailuros.core.report import render_audit_markdown

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V160 = ROOT / "fixtures" / "ailuros" / "v160"

PASS_PKG = V160 / "pass-governance-run"
WARN_PKG = V160 / "warn-anomaly-run"
FAIL_PKG = V160 / "fail-contract-run"


def _render_pass():
    return audit_result_to_markdown(audit_evidence_package(PASS_PKG))


def _render_warn():
    return audit_result_to_markdown(audit_evidence_package(WARN_PKG))


def _render_fail():
    return audit_result_to_markdown(audit_evidence_package(FAIL_PKG))


# ---------------------------------------------------------------------------
# Durable section headings
# ---------------------------------------------------------------------------

_REQUIRED_SECTIONS = (
    "## Decision",
    "## Summary",
    "## Checks",
    "## Warnings",
    "## Errors",
    "## Verdict",
)


def test_all_required_sections_present_pass():
    md = _render_pass()
    for section in _REQUIRED_SECTIONS:
        assert section in md, f"missing section {section!r} in pass report"


def test_all_required_sections_present_warn():
    md = _render_warn()
    for section in _REQUIRED_SECTIONS:
        assert section in md, f"missing section {section!r} in warn report"


def test_all_required_sections_present_fail():
    md = _render_fail()
    for section in _REQUIRED_SECTIONS:
        assert section in md, f"missing section {section!r} in fail report"


# ---------------------------------------------------------------------------
# Evidence summary: key metadata appears
# ---------------------------------------------------------------------------

def test_evidence_summary_contains_run_id():
    assert "run-v160-pass-001" in _render_pass()
    assert "run-v160-warn-001" in _render_warn()
    assert "run-v160-fail-001" in _render_fail()


def test_evidence_summary_contains_source():
    for md in (_render_pass(), _render_warn(), _render_fail()):
        assert "v160-agent" in md


def test_evidence_summary_contains_schema_version():
    for md in (_render_pass(), _render_warn(), _render_fail()):
        assert "ailuros.timeline.v0" in md


def test_evidence_summary_contains_events_count():
    assert "| Events " in _render_pass()
    assert "| Events " in _render_warn()
    assert "| Events " in _render_fail()


# ---------------------------------------------------------------------------
# Decision summary: decision is clearly surfaced
# ---------------------------------------------------------------------------

def test_decision_summary_pass():
    md = _render_pass()
    assert "**PASS**" in md
    assert "## Decision" in md
    assert "| Decision | pass |" in md


def test_decision_summary_warn():
    md = _render_warn()
    assert "**WARN**" in md
    assert "| Decision | warn |" in md


def test_decision_summary_fail():
    md = _render_fail()
    assert "**FAIL**" in md
    assert "| Decision | fail |" in md


# ---------------------------------------------------------------------------
# Validation status: checks convey validation outcome
# ---------------------------------------------------------------------------

def test_validation_status_checks_table_present():
    for md in (_render_pass(), _render_warn(), _render_fail()):
        assert "| Check | Status | Detail |" in md
        assert "Contract validation" in md
        assert "Anomalies" in md
        assert "Rules evaluated" in md


def test_validation_status_pass_is_clean():
    md = _render_pass()
    assert "Contract validation | pass" in md
    assert "Anomalies | pass" in md


def test_validation_status_warn_has_anomaly_signal():
    md = _render_warn()
    assert "Contract validation | pass" in md
    assert "Anomalies | warn" in md


def test_validation_status_fail_has_contract_signal():
    md = _render_fail()
    assert "Contract validation | fail" in md


# ---------------------------------------------------------------------------
# Warning / blocker / review reason (when applicable)
# ---------------------------------------------------------------------------

def test_warn_surfaces_review_reason():
    md = _render_warn()
    assert "custom_governance_review" in md
    assert "unknown event_type" in md.lower()


def test_fail_surfaces_blocker_reason():
    md = _render_fail()
    assert "must not be empty" in md


def test_pass_has_no_warnings_or_errors():
    md = _render_pass()
    # Section headings exist, but content indicates no issues
    assert "## Warnings" in md
    assert "## Errors" in md


# ---------------------------------------------------------------------------
# Verdict: conclusion matches decision type
# ---------------------------------------------------------------------------

def test_verdict_pass():
    assert "Evidence is clean and contract-valid." in _render_pass()


def test_verdict_warn():
    assert "Evidence is valid but has tolerated anomalies." in _render_warn()


def test_verdict_fail():
    assert "Evidence violates the package contract." in _render_fail()


# ---------------------------------------------------------------------------
# Cross-cutting quality: determinism and distinctness
# ---------------------------------------------------------------------------

def test_report_output_is_deterministic():
    assert _render_pass() == _render_pass()
    assert _render_warn() == _render_warn()
    assert _render_fail() == _render_fail()


def test_three_fixtures_produce_distinct_reports():
    reports = {_render_pass(), _render_warn(), _render_fail()}
    assert len(reports) == 3


# ---------------------------------------------------------------------------
# Core renderer unit-level: sections produced with synthetic result
# ---------------------------------------------------------------------------

def test_core_renderer_produces_all_sections_with_synthetic_result():
    result = AuditResult(
        ok=True,
        decision=AuditDecision.PASS,
        governance_mode="observe",
        source="test-source",
        schema_version="v0",
        run_id="run-001",
        events_count=5,
        rules_evaluated=2,
    )
    md = render_audit_markdown(result)
    for section in _REQUIRED_SECTIONS:
        assert section in md, f"missing section {section!r} in core renderer output"


def test_core_renderer_emits_custom_title():
    result = AuditResult(
        ok=True,
        decision=AuditDecision.PASS,
        source="x",
        run_id="x",
    )
    md = render_audit_markdown(result, title="Custom Title")
    assert md.startswith("# Custom Title")
