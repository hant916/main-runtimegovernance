from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from ailuros.audit.summary import build_audit_summary, build_run_summary
from ailuros.errors import AilurosDataCorruptionError
from ailuros.evidence.export import export_evidence
from ailuros.models import RuntimeEvent, RuntimeEventType
from ailuros.storage import SQLiteStorage


def export_audit_package(storage: SQLiteStorage, run_id: str) -> dict[str, Any]:
    events = storage.list_events(run_id)
    run = storage.get_run(run_id)
    audit_summary = build_audit_summary(events)
    run_summary = build_run_summary(storage, run_id)
    evidence_records = export_evidence(storage, run_id)

    return {
        "audit_package_version": "1",
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "run": {
            "agent_id": run.agent_id,
            "environment": run.environment.value,
            "status": run.status.value,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
        },
        "summary": {
            "decision": audit_summary.decision,
            "reason": audit_summary.reason,
            "tool": audit_summary.tool,
            "path_validation": audit_summary.path_validation,
            "event_count": run_summary.event_count,
            "decision_counts": dict(run_summary.decision_counts),
            "blocked_count": run_summary.blocked_count,
            "review_count": run_summary.review_count,
        },
        "timeline": _build_timeline(events),
        "decisions": _extract_decisions(events),
        "evidence": evidence_records,
        "validation": _build_validation(events),
        "replay": _get_replay_metadata(storage, run_id),
    }


def export_audit_package_json(storage: SQLiteStorage, run_id: str) -> str:
    package = export_audit_package(storage, run_id)
    return json.dumps(package, indent=2, default=str, sort_keys=True)


def _build_timeline(events: list[RuntimeEvent]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for event in events:
        entry: dict[str, Any] = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
        }
        if event.sequence is not None:
            entry["sequence"] = event.sequence
        timeline.append(entry)
    return timeline


def _extract_decisions(events: list[RuntimeEvent]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for event in events:
        if event.event_type is RuntimeEventType.GOVERNANCE_DECISION:
            decision: dict[str, Any] = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
            }
            if event.sequence is not None:
                decision["sequence"] = event.sequence
            decision.update(event.payload)
            decisions.append(decision)
    return decisions


def _build_validation(events: list[RuntimeEvent]) -> dict[str, Any]:
    path_validations: list[dict[str, Any]] = []
    for event in events:
        if event.event_type is RuntimeEventType.PATH_VALIDATION_RESULT:
            entry: dict[str, Any] = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
            }
            if event.sequence is not None:
                entry["sequence"] = event.sequence
            entry.update(event.payload)
            path_validations.append(entry)
    return {"path_validations": path_validations}


def _get_replay_metadata(storage: SQLiteStorage, run_id: str) -> dict[str, Any] | None:
    try:
        conn = sqlite3.connect(
            f"file:{storage.path.resolve()}?mode=ro",
            uri=True,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM replay_runs WHERE run_id = ? ORDER BY created_at DESC",
            (run_id,),
        ).fetchall()
        conn.close()
    except sqlite3.Error as exc:
        raise AilurosDataCorruptionError(
            f"replay_runs query failed for run_id={run_id}"
        ) from exc

    if not rows:
        return None

    results: list[dict[str, Any]] = []
    for row in rows:
        result: dict[str, Any] = {
            "replay_id": row["replay_id"],
            "run_id": row["run_id"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        try:
            result["key_events"] = json.loads(row["key_events_json"])
        except json.JSONDecodeError:
            result["key_events"] = []
        try:
            result["metadata"] = json.loads(row["metadata_json"])
        except json.JSONDecodeError:
            result["metadata"] = {}
        results.append(result)

    return {"replay_runs": results}
