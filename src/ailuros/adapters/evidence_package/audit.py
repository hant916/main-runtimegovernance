from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ailuros.adapters.evidence_package.rules import evaluate_rules
from ailuros.adapters.evidence_package.validator import (
    validate_evidence_package_contract,
)
from ailuros.core.audit import AuditDecision, AuditResult
from ailuros.evidence_conformance import (
    EvidenceInconsistency,
    detect_evidence_inconsistencies,
)
from ailuros.evidence_normalization import normalize_external_evidence_event


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


def _timeline_events(package_dir: str | Path) -> list[dict[str, Any]]:
    """Read canonical, wrapper-normalized events from a package timeline.

    Mirrors the conformance reader so the consistency path sees exactly the same
    canonical events the capability evaluator sees. Returns ``[]`` for absent or
    unreadable timelines; the consistency path must never fabricate events.
    """
    timeline_path = Path(package_dir) / "timeline.json"
    if not timeline_path.is_file():
        return []
    try:
        raw = json.loads(timeline_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, dict):
        return []
    events = raw.get("events")
    if not isinstance(events, list):
        return []
    return [
        normalize_external_evidence_event(event)
        for event in events
        if isinstance(event, dict)
    ]


def _format_inconsistency(finding: EvidenceInconsistency) -> str:
    """Render one grounded contradiction as a stable, evidence-grounded message.

    The message carries the deterministic rule id, the distinct claim values, and
    the exact evidence ids that were compared, so a reviewer can locate the two
    conflicting events without any raw-text parsing.
    """
    values = ", ".join(finding.values)
    ids = ", ".join(finding.evidence_ids)
    return (
        f"inconsistent_evidence[{finding.rule_id}] {finding.subject}: "
        f"[{values}] ({ids})"
    )


def audit_evidence_package(package_dir: str | Path) -> AuditResult:
    """Produce a post-run :class:`AuditResult` for a canonical evidence package.

    This validates the package contract and applies the minimal post-run rule
    set to derive a pass/warn/fail decision. It is post-run validation, not
    runtime governance: no allow/review/block control is performed.

    After the structural rules, already-ingested structured evidence is checked
    for deterministic contradictions. A contradiction escalates a tolerated
    pass/warn into ``fail`` and is recorded as an explicit, evidence-grounded
    ``inconsistent_evidence`` error — never as an ordinary unknown-event warning.
    """
    validation = validate_evidence_package_contract(package_dir)
    decision, rules_evaluated = evaluate_rules(validation)

    errors = list(validation.errors)
    findings = detect_evidence_inconsistencies(_timeline_events(package_dir))
    if findings:
        decision = AuditDecision.FAIL
        errors.extend(_format_inconsistency(finding) for finding in findings)

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
        errors=errors,
    )
