from __future__ import annotations

from datetime import UTC, datetime

from ailuros.audit import build_audit_summary
from ailuros.models import RuntimeEvent, RuntimeEventType


def test_audit_summary_uses_stored_governance_evidence_only():
    summary = build_audit_summary(
        [
            make_event(
                "evt-1",
                RuntimeEventType.TOOL_CALL_REQUESTED,
                {"tool_name": "payment.issue_refund"},
            ),
            make_event(
                "evt-2",
                RuntimeEventType.GOVERNANCE_DECISION,
                {"decision": "require_review", "reason": "refund requires approval"},
            ),
            make_event("evt-3", RuntimeEventType.PATH_VALIDATION_RESULT, {"valid": False}),
        ]
    )

    assert summary.decision == "require_review"
    assert summary.reason == "refund requires approval"
    assert summary.tool == "payment.issue_refund"
    assert summary.path_validation == "invalid"


def test_audit_summary_reports_unknowns_when_evidence_is_absent():
    summary = build_audit_summary([make_event("evt-1", RuntimeEventType.RUN_STARTED)])

    assert summary.decision == "unknown"
    assert summary.reason == "unknown"
    assert summary.tool == "unknown"
    assert summary.path_validation == "absent"


def test_audit_summary_can_use_tool_stored_on_decision_event():
    summary = build_audit_summary(
        [
            make_event(
                "evt-1",
                RuntimeEventType.GOVERNANCE_DECISION,
                {
                    "decision": "block",
                    "reason": "tool denied",
                    "tool_name": "filesystem.write",
                },
            )
        ]
    )

    assert summary.tool == "filesystem.write"


def make_event(
    event_id: str,
    event_type: RuntimeEventType,
    payload: dict | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        run_id="run-1",
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload or {},
    )
