from datetime import UTC, datetime

import pytest

from ailuros.models import RuntimeEvent, RuntimeEventType
from ailuros.path import ExpectedPath, PathValidator


def tool_call_event(
    event_id: str,
    tool_name: str | None = None,
    *,
    event_type: RuntimeEventType = RuntimeEventType.TOOL_CALL_REQUESTED,
    sequence: int | None = None,
    payload: dict[str, object] | None = None,
) -> RuntimeEvent:
    if payload is None:
        payload = {} if tool_name is None else {"tool_name": tool_name}
    return RuntimeEvent(
        event_id=event_id,
        run_id="run_1",
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload,
        sequence=sequence,
    )


def test_valid_required_path_uses_tool_call_requested_events():
    expected_path = ExpectedPath(
        path_id="refund",
        required_tool_calls=["order.get_status", "payment.issue_refund"],
    )
    events = [
        tool_call_event("evt_1", "order.get_status"),
        tool_call_event("evt_2", "ignored", event_type=RuntimeEventType.TOOL_CALL_EXECUTED),
        tool_call_event("evt_3", "payment.issue_refund"),
    ]

    result = PathValidator.validate(expected_path, events)

    assert result.valid is True
    assert result.missing_required == []
    assert result.observed_required == ["order.get_status", "payment.issue_refund"]


def test_missing_required_tool_call_fails_closed():
    expected_path = ExpectedPath(path_id="refund", required_tool_calls=["payment.issue_refund"])
    events = [tool_call_event("evt_1", "order.get_status")]

    result = PathValidator.validate(expected_path, events)

    assert result.valid is False
    assert result.missing_required == ["payment.issue_refund"]


def test_forbidden_tool_call_observed_fails_closed():
    expected_path = ExpectedPath(path_id="refund", forbidden_tool_calls=["payment.issue_refund"])
    events = [tool_call_event("evt_1", "payment.issue_refund")]

    result = PathValidator.validate(expected_path, events)

    assert result.valid is False
    assert result.forbidden_observed == ["payment.issue_refund"]


def test_unexpected_tool_call_is_informational():
    expected_path = ExpectedPath(path_id="status", required_tool_calls=["order.get_status"])
    events = [
        tool_call_event("evt_1", "order.get_status"),
        tool_call_event("evt_2", "customer.lookup"),
    ]

    result = PathValidator.validate(expected_path, events)

    assert result.valid is True
    assert result.unexpected_tool_calls == ["customer.lookup"]


def test_duplicate_required_tool_calls_are_ordered_repeated_requirements():
    expected_path = ExpectedPath(
        path_id="repeat",
        required_tool_calls=["order.get_status", "order.get_status"],
    )
    one_call_result = PathValidator.validate(
        expected_path,
        [tool_call_event("evt_1", "order.get_status")],
    )
    two_call_result = PathValidator.validate(
        expected_path,
        [
            tool_call_event("evt_1", "order.get_status"),
            tool_call_event("evt_2", "order.get_status"),
        ],
    )

    assert one_call_result.valid is False
    assert one_call_result.missing_required == ["order.get_status"]
    assert two_call_result.valid is True
    assert two_call_result.observed_required == ["order.get_status", "order.get_status"]


def test_empty_events_valid_only_without_required_calls():
    assert PathValidator.validate(ExpectedPath(path_id="empty"), []).valid is True

    result = PathValidator.validate(
        ExpectedPath(path_id="empty", required_tool_calls=["payment.issue_refund"]),
        [],
    )

    assert result.valid is False
    assert result.missing_required == ["payment.issue_refund"]


def test_malformed_tool_call_payload_returns_invalid_result():
    expected_path = ExpectedPath(path_id="malformed")
    events = [tool_call_event("evt_1", payload={"name": "payment.issue_refund"})]

    result = PathValidator.validate(expected_path, events)

    assert result.valid is False
    assert "evt_1 missing payload.tool_name" in result.reason


def test_sequence_order_used_when_all_tool_events_have_sequence():
    expected_path = ExpectedPath(
        path_id="refund",
        required_tool_calls=["order.get_status", "payment.issue_refund"],
    )
    events = [
        tool_call_event("evt_2", "payment.issue_refund", sequence=2),
        tool_call_event("evt_1", "order.get_status", sequence=1),
    ]

    result = PathValidator.validate(expected_path, events)

    assert result.valid is True
    assert result.observed_required == ["order.get_status", "payment.issue_refund"]


def test_provided_order_used_when_any_tool_event_lacks_sequence():
    expected_path = ExpectedPath(
        path_id="refund",
        required_tool_calls=["order.get_status", "payment.issue_refund"],
    )
    events = [
        tool_call_event("evt_2", "payment.issue_refund", sequence=2),
        tool_call_event("evt_1", "order.get_status"),
    ]

    result = PathValidator.validate(expected_path, events)

    assert result.valid is False
    assert result.missing_required == ["payment.issue_refund"]


def test_validation_does_not_mutate_events_or_event_list():
    expected_path = ExpectedPath(path_id="status", required_tool_calls=["order.get_status"])
    events = [tool_call_event("evt_1", "order.get_status", sequence=1)]
    original_events = list(events)
    original_dump = [event.model_dump() for event in events]

    PathValidator.validate(expected_path, events)

    assert events == original_events
    assert [event.model_dump() for event in events] == original_dump


def test_invalid_input_types_fail_loudly():
    with pytest.raises(TypeError):
        PathValidator.validate("not a path", [])

    with pytest.raises(TypeError):
        PathValidator.validate(ExpectedPath(path_id="path"), [object()])
