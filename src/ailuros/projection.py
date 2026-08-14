from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ailuros.core.execution import (
    ApprovalRecord,
    ApprovalState,
    ChangeSummary,
    DecisionSummary,
    EvidenceRef,
    ExecutionProjection,
    GovernanceContext,
    GovernanceContextConflict,
    Lifecycle,
    Outcome,
    RoleSummary,
    Scope,
    Validation,
)

if TYPE_CHECKING:
    from ailuros.signals import GovernanceSignal
    from ailuros.storage import SQLiteStorage

PROJECTION_VERSION = "1.0.0"

_OUTCOME_PRIORITY: dict[str, int] = {
    "block": 4,
    "require_review": 3,
}

_VALIDATION_AGGREGATION_PRIORITY: dict[str, int] = {
    "failed": 3,
    "passed": 2,
    "not_run": 1,
}

_AUDIT_DECISIONS: frozenset[str] = frozenset({"pass", "warn", "fail"})


def _project_decision_domain(payload: dict[str, Any], decision: str) -> str:
    if payload.get("tool_name"):
        return "runtime_action"
    explicit_domain = payload.get("domain", "")
    if explicit_domain == "execution_control":
        return "execution_control"
    if explicit_domain == "post_run_audit" or decision in _AUDIT_DECISIONS:
        return "post_run_audit"
    return "source_preserved_unknown"


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


_GOVERNANCE_CONTEXT_FIELDS: tuple[str, ...] = (
    "principal_ref",
    "workflow_ref",
    "invocation_ref",
    "policy_snapshot_ref",
)


def _project_governance_context(
    events: list[dict[str, Any]],
) -> GovernanceContext | None:
    field_values: dict[str, dict[str, set[str]]] = {
        field: {} for field in _GOVERNANCE_CONTEXT_FIELDS
    }
    source_pointers: list[str] = []
    seen_pointers: set[str] = set()

    for event in events:
        if event.get("event_type") != "governance_context":
            continue
        event_id: str = event.get("event_id", "")
        payload: dict[str, Any] = event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        if event_id and event_id not in seen_pointers:
            seen_pointers.add(event_id)
            source_pointers.append(event_id)

        payload_pointers = payload.get("source_pointers")
        if isinstance(payload_pointers, list):
            for pointer in payload_pointers:
                if isinstance(pointer, str) and pointer and pointer not in seen_pointers:
                    seen_pointers.add(pointer)
                    source_pointers.append(pointer)

        for field in _GOVERNANCE_CONTEXT_FIELDS:
            value = payload.get(field)
            if not isinstance(value, str) or not value:
                continue
            field_values[field].setdefault(value, set())
            if event_id:
                field_values[field][value].add(event_id)

    if not any(field_values[field] for field in _GOVERNANCE_CONTEXT_FIELDS):
        return None

    resolved: dict[str, str | None] = {}
    inconsistencies: list[GovernanceContextConflict] = []
    for field in _GOVERNANCE_CONTEXT_FIELDS:
        distinct = field_values[field]
        if not distinct:
            resolved[field] = None
        elif len(distinct) == 1:
            resolved[field] = next(iter(distinct))
        else:
            resolved[field] = None
            pointers = sorted(
                {event_id for ids in distinct.values() for event_id in ids}
            )
            inconsistencies.append(
                GovernanceContextConflict(
                    field=field,
                    values=sorted(distinct),
                    source_pointers=pointers,
                )
            )

    return GovernanceContext(
        principal_ref=resolved["principal_ref"],
        workflow_ref=resolved["workflow_ref"],
        invocation_ref=resolved["invocation_ref"],
        policy_snapshot_ref=resolved["policy_snapshot_ref"],
        source_pointers=source_pointers,
        inconsistencies=inconsistencies,
    )


_APPROVAL_EVENT_TYPES: frozenset[str] = frozenset({"approval_evidence"})

_APPROVED_DECISIONS: frozenset[str] = frozenset(
    {"approved", "approve", "granted"}
)

_DENIED_DECISIONS: frozenset[str] = frozenset(
    {"denied", "deny", "rejected", "reject", "declined"}
)


def _normalize_approval_state(decision: str | None) -> ApprovalState:
    if decision is None:
        return ApprovalState.UNKNOWN
    lowered = decision.strip().lower()
    if lowered in _APPROVED_DECISIONS:
        return ApprovalState.APPROVED
    if lowered in _DENIED_DECISIONS:
        return ApprovalState.DENIED
    return ApprovalState.UNKNOWN


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
    approval_records: list[ApprovalRecord] = []

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
            projected_domain = _project_decision_domain(payload, decision_type)

            decisions.append(
                DecisionSummary(
                    domain=domain,
                    decision=decision_type,
                    projected_domain=projected_domain,
                )
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

        elif event_type == "governance_context":
            evidence_refs.append(EvidenceRef(event_id=event_id))

        elif event_type in _APPROVAL_EVENT_TYPES:
            subject = payload.get("subject")
            if isinstance(subject, str) and subject:
                action = payload.get("action")
                required = payload.get("required")
                decision = payload.get("decision")
                approver_ref = payload.get("approver_ref")
                approval_records.append(
                    ApprovalRecord(
                        subject=subject,
                        action=action if isinstance(action, str) and action else None,
                        required=required if isinstance(required, bool) else None,
                        decision=(
                            decision if isinstance(decision, str) and decision else None
                        ),
                        state=_normalize_approval_state(
                            decision if isinstance(decision, str) and decision else None
                        ),
                        approver_ref=(
                            approver_ref
                            if isinstance(approver_ref, str) and approver_ref
                            else None
                        ),
                        timestamp=timestamp or datetime.now(UTC),
                        evidence_refs=[EvidenceRef(event_id=event_id)]
                        if event_id
                        else [],
                        source={"event_id": event_id, "event_type": event_type},
                    )
                )
            evidence_refs.append(EvidenceRef(event_id=event_id))

    validation = _resolve_validation(validation_presence)
    governance_context = _project_governance_context(events)

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
        governance_context=governance_context,
        approval_records=approval_records,
    )


def rebuild_projections_and_signals(
    storage: SQLiteStorage,
    run_id: str,
    *,
    source: str = "rebuild",
    schema_version: str = "1.0",
) -> tuple[ExecutionProjection, list[GovernanceSignal]]:
    from ailuros.signals import derive_signals

    events = storage.list_events(run_id)
    event_dicts: list[dict[str, Any]] = [
        {
            "event_id": e.event_id,
            "event_type": e.event_type.value,
            "timestamp": e.timestamp,
            "payload": e.payload,
            "step_id": e.step_id,
        }
        for e in events
    ]

    projection = build_execution_projection(
        run_id=run_id,
        source=source,
        events=event_dicts,
        schema_version=schema_version,
    )

    signals = derive_signals(projection)

    projection_dict = projection.model_dump(mode="json")
    storage.upsert_projection(
        run_id=run_id,
        projection_schema=f"execution_summary/v{schema_version}",
        projection_version=PROJECTION_VERSION,
        source=source,
        projection_json=projection_dict,
        lifecycle_status=projection.lifecycle.value,
        outcome_summary=projection.outcome.value,
        validation_summary=projection.validation.value,
    )

    signal_dicts = [s.model_dump(mode="json") for s in signals]
    storage.replace_signals(run_id, signal_dicts)

    return projection, signals
