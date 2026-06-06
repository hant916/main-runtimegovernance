from __future__ import annotations

from ailuros.core.audit import AuditResult
from ailuros.core.report import render_audit_markdown

_REPORT_TITLE = "Evidence Package Audit Report"


def audit_result_to_markdown(result: AuditResult) -> str:
    """Render an :class:`AuditResult` as a deterministic Markdown audit report.

    Thin, source-neutral wrapper over the generic core renderer. Output is stable
    for a given result; it is post-run audit reporting only, with no runtime
    control surface.
    """
    return render_audit_markdown(result, title=_REPORT_TITLE)
