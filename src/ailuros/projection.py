from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ailuros.core.execution import (
    ChangeSummary,
    DecisionSummary,
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    RoleSummary,
    Scope,
    Validation,
)

_OUTCOME_PRIORITY: dict[str, int] = {
    "block": 4,
    "require_review": 3,
}

_VALIDATION_AGGREGATION_PRIORITY: dict[str, int] = {
    "failed": 3,
    "passed": 2,
    "not_run": 1,
}


def _resolve_validation(validation_presence: set[str]) -> Validation:
    if not validation_presence:
        return Validation.UNKNOWN
    if "failed" in validation_presence:
        return Validation.FAILED
    if "passed" in validation_presence and "not_run" in validation_presence:
        return Validation.PARTIAL
    if "passed" in validation_presence:
        return Validation.PASSED
    if "not_run" in validation_presence:
        return Validation.NOT_RUN
    return Validation.UNKNOWN


def build_execution_projection(
    run_id: str,
    source: str,
    events: list[dict[str, Any]],
    *,
    schema_version: str = "1.0",
) -> ExecutionProjection:
    started_at: datetime | None = None
    completed_at: datetime | None = None
    lifecycle = Lifecycle.UNKNOWN
    outcome = Outcome.UNKNOWN

    decisions: list[DecisionSummary] = []
    outcome_priority = 0

    step_ids: set[str] = set()
    decision_count = 0
    evidence_refs: list[EvidenceRef] = []

    validation_presence: set[str] = set()
    scope_violated: bool = False
    scope_clean: bool = False
    role_names: set[str] = set()
    change_descriptions: list[str] = []

    for event in events:
        event_type: str = event.get("event_type", "")
        event_id: str = event.get("event_id", "")
        timestamp: datetime | None = event.get("timestamp")
        payload: dict[str, Any] = event.get("payload", {})
        step_id: str | None = event.get("step_id")

        if step_id:
            step_ids.add(step_id)

        if event_type == "run_started":
            started_at = timestamp
            lifecycle = Lifecycle.RUNNING
            evidence_refs.append(EvidenceRef(event_id=event_id))

        elif event_type == "run_completed":
            completed_at = timestamp
            lifecycle = Lifecycle.COMPLETED
            evidence_refs.append(EvidenceRef(event_id=event_id))

        elif event_type == "run_failed":
            completed_at = timestamp
            lifecycle = Lifecycle.FAILED
            evidence_refs.append(EvidenceRef(event_id=event_id))

        elif event_type == "governance_decision":
            decision_count += 1
            decision_type = payload.get("decision", "")
            domain = payload.get("tool_name") or payload.get("domain") or "unknown"

            decisions.append(
                DecisionSummary(domain=domain, decision=decision_type)
            )
            evidence_refs.append(EvidenceRef(event_id=event_id))

            priority = _OUTCOME_PRIORITY.get(decision_type, 0)
            if priority > outcome_priority:
                outcome_priority = priority
                if decision_type == "block":
                    outcome = Outcome.BLOCKED
                elif decision_type == "require_review":
                    outcome = Outcome.REVIEW_REQUIRED

        elif event_type == "project_validation":
            status = payload.get("status", "")
            if status:
                validation_presence.add(status)
            evidence_refs.append(EvidenceRef(event_id=event_id))

        elif event_type == "project_scope":
            scope_status = payload.get("status", "")
            if scope_status == "violated":
                scope_violated = True
            elif scope_status == "clean":
                scope_clean = True

            changed_files = payload.get("changed_files")
            if isinstance(changed_files, list):
                for f in changed_files:
                    change_descriptions.append(str(f))

            evidence_refs.append(EvidenceRef(event_id=event_id))

        elif event_type == "runtime_role":
            role_name = payload.get("name", "")
            if role_name:
                role_names.add(role_name)
            evidence_refs.append(EvidenceRef(event_id=event_id))

    validation = _resolve_validation(validation_presence)

    if scope_violated:
        scope = Scope.VIOLATED
    elif scope_clean:
        scope = Scope.CLEAN
    else:
        scope = Scope.UNKNOWN

    if outcome == Outcome.UNKNOWN:
        if lifecycle == Lifecycle.COMPLETED:
            outcome = Outcome.SUCCESS
        elif lifecycle == Lifecycle.FAILED:
            outcome = Outcome.FAILED

    if started_at is None:
        started_at = datetime.now(UTC)

    return ExecutionProjection(
        run_id=run_id,
        source=source,
        schema_version=schema_version,
        lifecycle=lifecycle,
        outcome=outcome,
        validation=validation,
        scope=scope,
        started_at=started_at,
        completed_at=completed_at,
        step_count=len(step_ids),
        decision_count=decision_count,
        event_count=len(events),
        roles=[RoleSummary(name=name) for name in sorted(role_names)],
        changes=[ChangeSummary(description=d) for d in change_descriptions],
        decisions=decisions,
        evidence_refs=evidence_refs,
    )
