import pytest

from ailuros import AilurosRuntime, RuntimeEventType


def test_allowed_wrapped_tool_executes_and_records(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("hello")

    def add(x: int, y: int) -> int:
        return x + y

    result = runtime.wrap_tool("math.add", add)(run_id=run.run_id, x=1, y=2)

    assert not result.blocked
    assert result.result == 3
    assert result.decision.allowed
    event_types = [event.event_type for event in runtime.list_events(run.run_id)]
    assert RuntimeEventType.TOOL_CALL_EXECUTED in event_types
    assert RuntimeEventType.TOOL_RESULT_RECEIVED in event_types


def test_blocked_wrapped_tool_does_not_execute(tmp_path):
    policy = tmp_path / "block.json"
    policy.write_text(
        """
        {
          "policy_id": "block.tool",
          "version": "1",
          "decision": "block",
          "severity": "critical",
          "match": {"tool_name": "danger.run"}
        }
        """
    )
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite", policies=[policy])
    run = runtime.start_run("hello")
    called = False

    def dangerous() -> None:
        nonlocal called
        called = True

    result = runtime.wrap_tool("danger.run", dangerous)(run_id=run.run_id)

    assert result.blocked
    assert not called


def test_wrapped_tool_requires_run_id(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")

    with pytest.raises(ValueError, match="run_id"):
        runtime.wrap_tool("x", lambda: None)()
