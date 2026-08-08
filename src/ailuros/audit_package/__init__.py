from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ailuros.audit.summary import build_audit_summary, build_run_summary
from ailuros.audit_package.decision import decide_audit_package
from ailuros.audit_package.loader import load_audit_package
from ailuros.audit_package.models import (
    _AUDIT_PACKAGE_FILES,
    AuditPackage,
    AuditPackageLoadError,
    PackageValidationResult,
)
from ailuros.audit_package.validator import validate_audit_package
from ailuros.errors import AilurosNotFoundError
from ailuros.models import RuntimeEvent, RuntimeEventType
from ailuros.storage import SQLiteStorage

__all__ = [
    "AuditPackage",
    "AuditPackageLoadError",
    "PackageValidationResult",
    "decide_audit_package",
    "export_audit_package_to_dir",
    "load_audit_package",
    "validate_audit_package",
    "validate_audit_package_dir",
]


def validate_audit_package_dir(path: Path) -> PackageValidationResult:
    try:
        package = load_audit_package(path)
    except AuditPackageLoadError as exc:
        return PackageValidationResult(valid=False, decision="FAIL", reasons=exc.reasons)
    validation = validate_audit_package(package)
    return decide_audit_package(validation, package)


def export_audit_package_to_dir(
    storage: SQLiteStorage,
    run_id: str,
    output_dir: Path,
) -> Path:
    run = storage.get_run(run_id)
    events = storage.list_events(run_id)
    run_summary = build_run_summary(storage, run_id)
    audit_summary = build_audit_summary(events)

    decisions = _extract_decisions(events)
    evaluations = _get_evaluations(storage, run_id)
    regressions = _get_regressions(events)

    summary_md = _build_summary_md(
        run_id,
        events,
        run_summary,
        audit_summary,
        decisions,
        evaluations,
        regressions,
    )

    pkg_dir = output_dir / run_id
    pkg_dir.mkdir(parents=True, exist_ok=True)

    _write_json(pkg_dir / "run.json", _serialize_run(run))
    _write_jsonl(pkg_dir / "timeline.jsonl", [_serialize_timeline_event(e) for e in events])
    _write_json(pkg_dir / "decisions.json", decisions)
    _write_json(pkg_dir / "evaluations.json", evaluations)
    _write_json(pkg_dir / "regressions.json", regressions)
    _write_text(pkg_dir / "summary.md", summary_md)

    counts = {
        "timeline_events": len(events),
        "decisions": len(decisions),
        "evaluations": len(evaluations),
        "regressions": len(regressions),
    }
    _write_json(pkg_dir / "manifest.json", _build_manifest(run_id, counts))

    return pkg_dir


def _extract_decisions(events: list[RuntimeEvent]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for event in events:
        if event.event_type is RuntimeEventType.GOVERNANCE_DECISION:
            entry: dict[str, Any] = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
            }
            if event.sequence is not None:
                entry["sequence"] = event.sequence
            entry.update(event.payload)
            decisions.append(entry)
    return decisions


def _get_evaluations(storage: SQLiteStorage, run_id: str) -> list[dict[str, Any]]:
    try:
        evaluation = storage.get_evaluation(run_id)
        return [evaluation.model_dump(mode="json")]
    except AilurosNotFoundError:
        return []


def _get_regressions(events: list[RuntimeEvent]) -> list[dict[str, Any]]:
    regressions: list[dict[str, Any]] = []
    for event in events:
        if event.event_type is RuntimeEventType.REGRESSION_COMPARISON_RESULT:
            entry: dict[str, Any] = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
            }
            if event.sequence is not None:
                entry["sequence"] = event.sequence
            entry.update(event.payload)
            regressions.append(entry)
    return regressions


def _serialize_run(run: Any) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "agent_id": run.agent_id,
        "environment": run.environment.value,
        "status": run.status.value,
        "input": run.input,
        "user_id": run.user_id,
        "metadata": run.metadata,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


def _serialize_timeline_event(event: RuntimeEvent) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "timestamp": event.timestamp.isoformat(),
    }
    if event.sequence is not None:
        entry["sequence"] = event.sequence
    return entry


def _build_manifest(run_id: str, counts: dict[str, int]) -> dict[str, Any]:
    return {
        "schema_version": "ailuros.audit-package.v1",
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "files": list(_AUDIT_PACKAGE_FILES),
        "counts": counts,
        "package_status": "complete",
    }


def _build_summary_md(
    run_id: str,
    events: list[RuntimeEvent],
    run_summary: Any,
    audit_summary: Any,
    decisions: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    regressions: list[dict[str, Any]],
) -> str:
    tool_names = sorted(
        {
            event.payload.get("tool_name", "unknown")
            for event in events
            if event.payload and "tool_name" in event.payload
        }
    )

    decision_types = sorted({d.get("decision", "unknown") for d in decisions})

    eval_summary = "not_available"
    if evaluations:
        passed = sum(1 for e in evaluations if e.get("passed"))
        failed = sum(1 for e in evaluations if not e.get("passed"))
        eval_summary = f"{len(evaluations)} evaluation(s): {passed} passed, {failed} failed"

    reg_summary = "not_available"
    if regressions:
        passed = sum(1 for r in regressions if r.get("passed"))
        failed = sum(1 for r in regressions if not r.get("passed"))
        reg_summary = (
            f"{len(regressions)} regression comparison(s): {passed} passed, {failed} failed"
        )

    review_required = "yes" if run_summary.review_count > 0 else "no"

    md = (
        f"# Audit Summary: {run_id}\n\n"
        f"## Run Overview\n\n"
        f"- **Status**: {run_summary.status}\n"
        f"- **Run ID**: {run_summary.run_id}\n"
        f"- **Event count**: {run_summary.event_count}\n"
        f"- **Started**: {run_summary.started_at or 'not_available'}\n"
        f"- **Completed**: {run_summary.completed_at or 'not_available'}\n\n"
        f"## Decision\n\n"
        f"- **Decision**: {audit_summary.decision}\n"
        f"- **Reason**: {audit_summary.reason}\n"
        f"- **Tool**: {audit_summary.tool}\n"
        f"- **Path validation**: {audit_summary.path_validation}\n\n"
        f"## Tools / Actions\n\n"
        f"{', '.join(tool_names) if tool_names else 'none recorded'}\n\n"
        f"## Policy Decisions\n\n"
        f"{', '.join(decision_types) if decision_types else 'none recorded'}\n\n"
        f"## Evaluations\n\n"
        f"{eval_summary}\n\n"
        f"## Regressions\n\n"
        f"{reg_summary}\n\n"
        f"## Review Required\n\n"
        f"{review_required}\n"
    )
    return md


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    lines = "\n".join(json.dumps(r, default=str, sort_keys=True) for r in records)
    path.write_text(lines, encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
