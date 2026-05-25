from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ailuros.evaluation import (
    AllowedToolExpectation,
    BlockedToolExpectation,
    EvaluationCase,
    EvaluationService,
    EventSequenceContainsExpectation,
    GovernanceDecisionExpectation,
    PathValidationExpectation,
    ToolNotExecutedExpectation,
)
from ailuros.models import RuntimeEvent, RuntimeEventType


def event(
    sequence: int,
    event_type: RuntimeEventType,
    payload: dict[str, object] | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=f"evt_{sequence}",
        run_id="run_1",
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload or {},
        sequence=sequence,
    )


def evaluate(*expectations: object):
    events = [
        event(1, RuntimeEventType.RUN_STARTED),
        event(
            2,
            RuntimeEventType.GOVERNANCE_DECISION,
            {
                "decision": "deny",
                "allowed": False,
                "reason": "not asserted",
                "severity": "high",
            },
        ),
        event(
            3,
            RuntimeEventType.TOOL_CALL_BLOCKED,
            {"tool_name": "payment.issue_refund", "decision": "deny", "reason": "not asserted"},
        ),
        event(4, RuntimeEventType.AGENT_MESSAGE, {"message": "extra event allowed"}),
        event(
            5,
            RuntimeEventType.TOOL_CALL_EXECUTED,
            {"tool_name": "order.get_status", "arguments": {}, "metadata": {}},
        ),
        event(
            6,
            RuntimeEventType.TOOL_RESULT_RECEIVED,
            {"tool_name": "order.get_status", "arguments": {}, "result": {"ok": True}},
        ),
        event(7, RuntimeEventType.PATH_VALIDATION_RESULT, {"path_id": "refund", "valid": True}),
    ]
    case = EvaluationCase(id="case_1", name="case", expectations=list(expectations))

    return EvaluationService().evaluate(events, [case])[0]


def test_evaluation_case_passes_with_structured_evidence_and_extra_events():
    result = evaluate(
        GovernanceDecisionExpectation(decision="deny", allowed=False, severity="high"),
        BlockedToolExpectation(tool_name="payment.issue_refund", decision="deny"),
        AllowedToolExpectation(tool_name="order.get_status"),
        ToolNotExecutedExpectation(tool_name="payment.issue_refund"),
        PathValidationExpectation(path_id="refund", valid=True),
        EventSequenceContainsExpectation(
            event_types=[
                RuntimeEventType.RUN_STARTED,
                RuntimeEventType.TOOL_CALL_BLOCKED,
                RuntimeEventType.PATH_VALIDATION_RESULT,
            ]
        ),
    )

    assert result.case_id == "case_1"
    assert result.passed is True
    assert result.failures == []
    assert {item.expectation_type for item in result.evidence} == {
        "governance_decision",
        "blocked_tool",
        "allowed_tool",
        "tool_not_executed",
        "path_validation",
        "event_sequence_contains",
    }
    assert {item.sequence for item in result.evidence} >= {1, 2, 3, 5, 7}


@pytest.mark.parametrize(
    "expectation, expected_message",
    [
        (
            GovernanceDecisionExpectation(decision="allow", allowed=True),
            "Expected governance decision",
        ),
        (BlockedToolExpectation(tool_name="payment.capture"), "Expected blocked tool"),
        (
            AllowedToolExpectation(tool_name="payment.capture"),
            "Expected allowed/executed tool",
        ),
        (PathValidationExpectation(path_id="refund", valid=False), "Expected path validation"),
        (
            EventSequenceContainsExpectation(
                event_types=[
                    RuntimeEventType.PATH_VALIDATION_RESULT,
                    RuntimeEventType.TOOL_CALL_BLOCKED,
                ]
            ),
            "Expected event sequence",
        ),
    ],
)
def test_expectation_failures_include_expected_and_actual_context(expectation, expected_message):
    result = evaluate(expectation)

    assert result.passed is False
    assert len(result.failures) == 1
    assert expected_message in result.failures[0].message
    assert "actual=" in result.failures[0].message


def test_tool_not_executed_fails_when_blocked_tool_later_executes():
    events = [
        event(
            1,
            RuntimeEventType.TOOL_CALL_BLOCKED,
            {"tool_name": "payment.issue_refund", "decision": "deny"},
        ),
        event(
            2,
            RuntimeEventType.TOOL_RESULT_RECEIVED,
            {"tool_name": "payment.issue_refund", "result": {"ok": True}},
        ),
    ]
    case = EvaluationCase(
        id="case_1",
        name="case",
        expectations=[ToolNotExecutedExpectation(tool_name="payment.issue_refund")],
    )

    result = EvaluationService().evaluate(events, [case])[0]

    assert result.passed is False
    assert result.failures[0].expectation_type == "tool_not_executed"
    assert "not to execute after block" in result.failures[0].message
    assert [item.sequence for item in result.evidence] == [1, 2]


def test_tool_not_executed_fails_when_blocking_event_is_missing():
    result = evaluate(ToolNotExecutedExpectation(tool_name="payment.capture"))

    assert result.passed is False
    assert "blocking evidence" in result.failures[0].message


def test_unsupported_expectation_type_fails_validation_clearly():
    with pytest.raises(ValidationError) as exc_info:
        EvaluationCase(
            id="case_1",
            name="case",
            expectations=[{"type": "unknown_expectation"}],
        )

    assert "unknown_expectation" in str(exc_info.value)
