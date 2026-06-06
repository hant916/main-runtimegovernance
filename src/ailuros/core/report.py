from __future__ import annotations

from ailuros.core.audit import AuditDecision, AuditResult

# Source-neutral verdict text keyed by decision. These describe the outcome of
# validating an already-completed run's evidence; they are not runtime controls.
_VERDICT_TEXT = {
    AuditDecision.PASS: "Evidence is clean and contract-valid.",
    AuditDecision.WARN: "Evidence is valid but has tolerated anomalies.",
    AuditDecision.FAIL: "Evidence violates the package contract.",
}

_NA = "n/a"


def _scalar(value: object) -> str:
    """Render an optional scalar deterministically and source-neutrally."""
    if value is None:
        return _NA
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_audit_markdown(
    result: AuditResult,
    *,
    title: str = "Audit Report",
) -> str:
    """Render a deterministic, source-neutral Markdown report from an ``AuditResult``.

    The output is stable for a given result: warning and error order is preserved
    exactly as produced by validation, and no timestamps or environment-specific
    data are emitted. Sections are Decision, Summary, Checks, Warnings, Errors,
    and Verdict.

    This is a post-run audit report. It records an after-the-fact judgement about
    captured evidence; it carries no runtime allow/review/block control.
    """
    lines: list[str] = []

    lines.append(f"# {title}")
    lines.append("")

    # Decision
    lines.append("## Decision")
    lines.append("")
    lines.append(f"**{result.decision.value.upper()}**")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Decision | {result.decision.value} |")
    lines.append(f"| OK | {_scalar(result.ok)} |")
    lines.append(f"| Governance mode | {_scalar(result.governance_mode)} |")
    lines.append(f"| Source | {_scalar(result.source)} |")
    lines.append(f"| Schema version | {_scalar(result.schema_version)} |")
    lines.append(f"| Run ID | {_scalar(result.run_id)} |")
    lines.append(f"| Events | {_scalar(result.events_count)} |")
    lines.append(f"| Rules evaluated | {_scalar(result.rules_evaluated)} |")
    lines.append("")

    # Checks
    error_count = len(result.errors)
    warning_count = len(result.warnings)
    contract_status = "fail" if error_count else "pass"
    anomaly_status = "warn" if warning_count else "pass"
    lines.append("## Checks")
    lines.append("")
    lines.append("| Check | Status | Detail |")
    lines.append("|---|---|---|")
    lines.append(f"| Contract validation | {contract_status} | {error_count} error(s) |")
    lines.append(f"| Anomalies | {anomaly_status} | {warning_count} warning(s) |")
    lines.append(f"| Rules evaluated | info | {result.rules_evaluated} |")
    lines.append("")

    # Warnings
    lines.append("## Warnings")
    lines.append("")
    if result.warnings:
        for warning in result.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("None.")
    lines.append("")

    # Errors
    lines.append("## Errors")
    lines.append("")
    if result.errors:
        for error in result.errors:
            lines.append(f"- {error}")
    else:
        lines.append("None.")
    lines.append("")

    # Verdict
    lines.append("## Verdict")
    lines.append("")
    lines.append(_VERDICT_TEXT[result.decision])
    lines.append("")

    return "\n".join(lines)
