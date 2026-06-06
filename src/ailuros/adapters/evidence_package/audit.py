from __future__ import annotations

import json
from pathlib import Path

from ailuros.adapters.evidence_package.rules import evaluate_rules
from ailuros.adapters.evidence_package.validator import (
    validate_evidence_package_contract,
)
from ailuros.core.audit import AuditDecision, AuditResult


def _read_governance_mode(package_dir: str | Path) -> str | None:
    """Best-effort read of the manifest's declared governance mode.

    Returns ``None`` when the manifest is absent, unreadable, or omits the field.
    This is contextual metadata only; it never influences the audit decision.
    """
    manifest_path = Path(package_dir) / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(manifest, dict):
        mode = manifest.get("governance_mode")
        if isinstance(mode, str) and mode:
            return mode
    return None


def audit_evidence_package(package_dir: str | Path) -> AuditResult:
    """Produce a post-run :class:`AuditResult` for a canonical evidence package.

    This validates the package contract and applies the minimal post-run rule
    set to derive a pass/warn/fail decision. It is post-run validation, not
    runtime governance: no allow/review/block control is performed.
    """
    validation = validate_evidence_package_contract(package_dir)
    decision, rules_evaluated = evaluate_rules(validation)

    return AuditResult(
        ok=decision != AuditDecision.FAIL,
        decision=decision,
        governance_mode=_read_governance_mode(package_dir),
        source=validation.source,
        schema_version=validation.schema_version,
        run_id=validation.run_id,
        events_count=validation.events_count,
        rules_evaluated=rules_evaluated,
        warnings=list(validation.warnings),
        errors=list(validation.errors),
    )
