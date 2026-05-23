import pytest

from ailuros import AilurosRuntime, GovernanceDecisionType, RuntimeEventType
from ailuros.errors import AilurosNotFoundError
from ailuros.path import ExpectedPath, PathValidationResult


def path_validation_events(runtime: AilurosRuntime, run_id: str):
    return [
        event
        for event in runtime.list_events(run_id)
        if event.event_type == RuntimeEventType.PATH_VALIDATION_RESULT
    ]


def test_validate_path_records_one_result_event(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("refund")
    runtime.before_tool_call(run.run_id, "order.get_status")
    expected_path = ExpectedPath(
        path_id="refund",
        required_tool_calls=["order.get_status"],
    )

    result = runtime.validate_path(run.run_id, expected_path)

    assert isinstance(result, PathValidationResult)
    events = path_validation_events(runtime, run.run_id)
    assert len(events) == 1
    assert events[0].payload == result.model_dump(mode="json")
    assert runtime.list_events(run.run_id)[-1].event_type == RuntimeEventType.PATH_VALIDATION_RESULT


def test_validate_path_records_invalid_result(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("refund")
    expected_path = ExpectedPath(
        path_id="refund",
        required_tool_calls=["payment.issue_refund"],
    )

    result = runtime.validate_path(run.run_id, expected_path)

    assert result.valid is False
    events = path_validation_events(runtime, run.run_id)
    assert len(events) == 1
    assert events[0].payload == result.model_dump(mode="json")


def test_validate_path_unknown_run_records_no_event(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("refund")
    expected_path = ExpectedPath(path_id="refund")

    with pytest.raises(AilurosNotFoundError):
        runtime.validate_path("run_missing", expected_path)

    assert path_validation_events(runtime, run.run_id) == []


def test_before_tool_call_does_not_validate_path_automatically(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("refund")
    ExpectedPath(path_id="refund", required_tool_calls=["payment.issue_refund"])

    decision = runtime.before_tool_call(run.run_id, "order.get_status")

    assert decision.decision is GovernanceDecisionType.ALLOW
    assert decision.allowed is True
    assert path_validation_events(runtime, run.run_id) == []
