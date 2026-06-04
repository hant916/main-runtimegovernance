import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from ailuros import (
    Environment,
    GovernanceDecision,
    GovernanceDecisionType,
    Policy,
    Run,
    RunStatus,
    RuntimeEvent,
    RuntimeEventType,
    Severity,
)


def test_runtime_event_type_contains_canonical_events() -> None:
    values = {event.value for event in RuntimeEventType}

    assert "run_started" in values
    assert "payload_redacted" in values
    assert len(values) == 26


def test_models_serialize_to_json() -> None:
    run = Run(
        run_id="run_1",
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    event = RuntimeEvent(
        event_id="evt_1",
        run_id=run.run_id,
        event_type=RuntimeEventType.RUN_STARTED,
        timestamp=datetime.now(UTC),
        payload={"ok": True},
    )

    assert "run_1" in run.model_dump_json()
    assert "run_started" in event.model_dump_json()


def test_invalid_enum_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RuntimeEvent(
            event_id="evt_1",
            run_id="run_1",
            event_type="unknown",
            timestamp=datetime.now(UTC),
        )


def test_policy_accepts_valid_json_definition() -> None:
    policy = Policy(
        policy_id="refund.high",
        version="1",
        decision="require_review",
        severity=Severity.HIGH,
        match={"tool_name": "payment.issue_refund", "arguments.amount_eur": {"gt": 500}},
    )

    assert policy.match["arguments.amount_eur"]["gt"] == 500


def _decision(decision_type: GovernanceDecisionType, **kwargs: Any) -> GovernanceDecision:
    return GovernanceDecision(
        decision_id=str(uuid.uuid4()),
        run_id="test-run",
        decision=decision_type,
        allowed=decision_type == GovernanceDecisionType.ALLOW,
        reason="test reason",
        created_at=datetime.now(tz=UTC),
        **kwargs,
    )


def test_decision_carries_evidence_metadata_for_allow() -> None:
    decision = _decision(
        GovernanceDecisionType.ALLOW,
        risk_level=Severity.LOW,
        evidence_refs=["policy-match-001"],
        input_hash="abc123",
        tool_name="test.tool",
    )
    dumped = decision.model_dump(mode="json")
    assert dumped["decision"] == "allow"
    assert dumped["allowed"] is True
    assert dumped["risk_level"] == "low"
    assert dumped["evidence_refs"] == ["policy-match-001"]
    assert dumped["input_hash"] == "abc123"
    assert dumped["tool_name"] == "test.tool"


def test_decision_carries_evidence_metadata_for_block() -> None:
    decision = _decision(
        GovernanceDecisionType.BLOCK,
        risk_level=Severity.HIGH,
        evidence_refs=["policy-block-002", "risk-flag"],
        input_hash="def456",
        tool_name="dangerous.action",
    )
    dumped = decision.model_dump(mode="json")
    assert dumped["decision"] == "block"
    assert dumped["allowed"] is False
    assert dumped["risk_level"] == "high"
    assert dumped["evidence_refs"] == ["policy-block-002", "risk-flag"]
    assert dumped["input_hash"] == "def456"
    assert dumped["tool_name"] == "dangerous.action"


def test_decision_carries_evidence_metadata_for_review() -> None:
    decision = _decision(
        GovernanceDecisionType.REQUIRE_REVIEW,
        risk_level=Severity.MEDIUM,
        evidence_refs=["review-trigger-003"],
        input_hash="ghi789",
        tool_name="suspicious.call",
    )
    dumped = decision.model_dump(mode="json")
    assert dumped["decision"] == "require_review"
    assert dumped["allowed"] is False
    assert dumped["risk_level"] == "medium"
    assert dumped["evidence_refs"] == ["review-trigger-003"]
    assert dumped["input_hash"] == "ghi789"
    assert dumped["tool_name"] == "suspicious.call"


def test_evidence_fields_default_to_empty_safe_values() -> None:
    decision = _decision(GovernanceDecisionType.ALLOW)
    dumped = decision.model_dump(mode="json")
    assert dumped["risk_level"] == "low"
    assert dumped["evidence_refs"] == []
    assert dumped["input_hash"] is None
    assert dumped["tool_name"] is None


def test_decision_serialization_is_deterministic() -> None:
    now = datetime.now(UTC)
    d1 = GovernanceDecision(
        decision_id="dec_deterministic",
        run_id="run-1",
        decision=GovernanceDecisionType.ALLOW,
        allowed=True,
        reason="test",
        risk_level=Severity.LOW,
        evidence_refs=["ref-a", "ref-b"],
        input_hash="hash1",
        tool_name="tool.one",
        created_at=now,
    )
    d2 = GovernanceDecision(
        decision_id="dec_deterministic",
        run_id="run-1",
        decision=GovernanceDecisionType.ALLOW,
        allowed=True,
        reason="test",
        risk_level=Severity.LOW,
        evidence_refs=["ref-a", "ref-b"],
        input_hash="hash1",
        tool_name="tool.one",
        created_at=now,
    )
    assert d1.model_dump(mode="json") == d2.model_dump(mode="json")
