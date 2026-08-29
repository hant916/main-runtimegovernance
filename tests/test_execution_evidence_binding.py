from __future__ import annotations

from ailuros import AilurosRuntime, GovernanceDecisionType, RuntimeEventType
from ailuros.replay import ReplayService


def _events_by_type(runtime: AilurosRuntime, run_id: str, event_type: RuntimeEventType):
    return [event for event in runtime.list_events(run_id) if event.event_type is event_type]


def test_allowed_execution_outcome_replays_with_its_decision_id(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("allowed")

    result = runtime.wrap_tool("governed.tool", lambda: "returned")(run_id=run.run_id)

    assert result.decision.decision is GovernanceDecisionType.ALLOW
    result_event = _events_by_type(runtime, run.run_id, RuntimeEventType.TOOL_RESULT_RECEIVED)[0]
    assert result_event.payload["result"] == "returned"
    assert result_event.payload["decision_id"] == result.decision.decision_id
    replay = ReplayService(runtime.storage).build_timeline(run.run_id)
    assert next(
        item["metadata"]["decision_id"]
        for item in replay
        if item["event_type"] == RuntimeEventType.TOOL_RESULT_RECEIVED.value
    ) == result.decision.decision_id


def test_failed_execution_outcome_replays_with_its_decision_id(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("failed")

    result = runtime.wrap_tool("governed.tool", lambda: 1 / 0)(run_id=run.run_id)

    assert result.error == "ZeroDivisionError: division by zero"
    outcome = _events_by_type(runtime, run.run_id, RuntimeEventType.TOOL_RESULT_RECEIVED)[0]
    assert outcome.payload["result"] is None
    assert outcome.payload["error"] == result.error
    assert outcome.payload["decision_id"] == result.decision.decision_id


def test_blocked_execution_records_non_execution_with_its_decision_id(tmp_path):
    policy = tmp_path / "block.json"
    policy.write_text(
        '{"policy_id":"block.tool","version":"1","decision":"block",'
        '"severity":"critical","match":{"tool_name":"governed.tool"}}'
    )
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite", policies=[policy])
    run = runtime.start_run("blocked")

    result = runtime.wrap_tool("governed.tool", lambda: "must not run")(run_id=run.run_id)

    blocked = _events_by_type(runtime, run.run_id, RuntimeEventType.TOOL_CALL_BLOCKED)[0]
    assert result.blocked is True
    assert blocked.payload["decision_id"] == result.decision.decision_id
    assert not _events_by_type(runtime, run.run_id, RuntimeEventType.TOOL_RESULT_RECEIVED)
