from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ailuros.audit.summary import build_audit_summary, build_run_summary
from ailuros.errors import AilurosNotFoundError
from ailuros.models import RuntimeEvent, RuntimeEventType
from ailuros.storage import SQLiteStorage

_AUDIT_PACKAGE_FILES = [
    "manifest.json",
    "run.json",
    "timeline.jsonl",
    "decisions.json",
    "evaluations.json",
    "regressions.json",
    "summary.md",
]


@dataclass(frozen=True)
class AuditPackage:
    path: Path
    manifest: Any
    run: Any
    timeline: list[Any]
    decisions: Any
    evaluations: Any
    regressions: Any
    summary: str


@dataclass(frozen=True)
class PackageValidationResult:
    valid: bool
    decision: str
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "decision": self.decision,
            "reasons": self.reasons,
        }


class AuditPackageLoadError(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def load_audit_package(path: Path) -> AuditPackage:
    package_dir = path.resolve()
    reasons = _missing_file_reasons(package_dir)
    if not package_dir.is_dir():
        raise AuditPackageLoadError([f"audit package directory not found: {path}"])
    if reasons:
        raise AuditPackageLoadError(reasons)

    loaded, parse_reasons = _load_package_records(package_dir)
    if parse_reasons:
        raise AuditPackageLoadError(parse_reasons)

    return AuditPackage(
        path=package_dir,
        manifest=loaded["manifest.json"],
        run=loaded["run.json"],
        timeline=_as_list(loaded["timeline.jsonl"]),
        decisions=loaded["decisions.json"],
        evaluations=loaded["evaluations.json"],
        regressions=loaded["regressions.json"],
        summary=(package_dir / "summary.md").read_text(encoding="utf-8"),
    )


def validate_audit_package(package: AuditPackage) -> PackageValidationResult:
    reasons = _structure_reasons(package)
    reasons.extend(_run_id_reasons(package))
    if reasons:
        return PackageValidationResult(valid=False, decision="FAIL", reasons=reasons)
    return PackageValidationResult(valid=True, decision="PASS", reasons=[])


def decide_audit_package(
    validation: PackageValidationResult,
    package: AuditPackage,
) -> PackageValidationResult:
    if not validation.valid:
        return validation
    decisions = list(_iter_dict_records(package.decisions))
    if any(_is_block_decision(decision) for decision in decisions):
        return PackageValidationResult(
            valid=True,
            decision="FAIL",
            reasons=["blocking governance decision present"],
        )
    if any(_is_review_decision(decision) for decision in decisions):
        return PackageValidationResult(
            valid=True,
            decision="REVIEW_REQUIRED",
            reasons=["review governance decision present"],
        )
    return validation


def validate_audit_package_dir(path: Path) -> PackageValidationResult:
    try:
        package = load_audit_package(path)
    except AuditPackageLoadError as exc:
        return PackageValidationResult(valid=False, decision="FAIL", reasons=exc.reasons)
    validation = validate_audit_package(package)
    return decide_audit_package(validation, package)


def _missing_file_reasons(package_dir: Path) -> list[str]:
    return [
        f"missing required file: {file_name}"
        for file_name in _AUDIT_PACKAGE_FILES
        if not (package_dir / file_name).is_file()
    ]


def _load_package_records(package_dir: Path) -> tuple[dict[str, Any], list[str]]:
    loaded: dict[str, Any] = {}
    reasons: list[str] = []
    for file_name in _AUDIT_PACKAGE_FILES:
        if file_name == "summary.md":
            continue
        try:
            if file_name == "timeline.jsonl":
                loaded[file_name] = _read_jsonl_file(package_dir / file_name)
            else:
                loaded[file_name] = _read_json_file(package_dir / file_name)
        except AuditPackageLoadError as exc:
            reasons.extend(exc.reasons)
    return loaded, reasons


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuditPackageLoadError(
            [f"malformed JSON in {path.name}: line {exc.lineno} column {exc.colno}"]
        ) from exc


def _read_jsonl_file(path: Path) -> list[Any]:
    records: list[Any] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise AuditPackageLoadError(
                [f"malformed JSONL in {path.name}: line {line_number} column {exc.colno}"]
            ) from exc
    return records


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _structure_reasons(package: AuditPackage) -> list[str]:
    reasons: list[str] = []
    if not isinstance(package.manifest, dict):
        reasons.append("manifest.json must contain a JSON object")
    if not isinstance(package.run, dict):
        reasons.append("run.json must contain a JSON object")
    for file_name, value in (
        ("timeline.jsonl", package.timeline),
        ("decisions.json", package.decisions),
        ("evaluations.json", package.evaluations),
        ("regressions.json", package.regressions),
    ):
        if not isinstance(value, list):
            reasons.append(f"{file_name} must contain a JSON array")
    return reasons


def _run_id_reasons(package: AuditPackage) -> list[str]:
    reasons: list[str] = []
    required_run_ids = {
        "manifest.json": _top_level_run_id(package.manifest),
        "run.json": _top_level_run_id(package.run),
    }
    for file_name, run_id in required_run_ids.items():
        if run_id is None:
            reasons.append(f"missing run_id in {file_name}")

    run_ids = _collect_run_ids(package)
    if len(set(run_ids)) > 1:
        reasons.append("mismatched run_id values: " + ", ".join(sorted(set(run_ids))))
    return reasons


def _top_level_run_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    run_id = value.get("run_id")
    return run_id if isinstance(run_id, str) and run_id else None


def _collect_run_ids(package: AuditPackage) -> list[str]:
    records: list[Any] = [
        package.manifest,
        package.run,
        package.timeline,
        package.decisions,
        package.evaluations,
        package.regressions,
    ]
    values: list[str] = []
    for record in records:
        values.extend(_find_run_ids(record))
    return values


def _find_run_ids(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        run_id = value.get("run_id")
        if isinstance(run_id, str) and run_id:
            found.append(run_id)
        for nested in value.values():
            found.extend(_find_run_ids(nested))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_run_ids(item))
    return found


def _iter_dict_records(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item


def _decision_value(record: dict[str, Any]) -> str:
    for key in ("decision", "action", "status"):
        value = record.get(key)
        if isinstance(value, str):
            return value.lower().replace("-", "_")
    return ""


def _is_block_decision(record: dict[str, Any]) -> bool:
    return _decision_value(record) in {"block", "blocked", "blocking", "fail", "failed"}


def _is_review_decision(record: dict[str, Any]) -> bool:
    return _decision_value(record) in {"require_review", "review", "review_required"}


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
