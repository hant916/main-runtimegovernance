from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ailuros.core.execution import (
    DecisionSummary,
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)

_OUTCOME_PRIORITY: dict[str, int] = {
    "block": 4,
    "require_review": 3,
}


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
        validation=Validation.UNKNOWN,
        scope=Scope.UNKNOWN,
        started_at=started_at,
        completed_at=completed_at,
        step_count=len(step_ids),
        decision_count=decision_count,
        event_count=len(events),
        decisions=decisions,
        evidence_refs=evidence_refs,
    )
