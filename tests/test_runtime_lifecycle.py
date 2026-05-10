import pytest

from ailuros import AilurosRuntime, RunStatus, RuntimeEventType
from ailuros.errors import AilurosNotFoundError


def test_runtime_lifecycle(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")

    run = runtime.start_run("hello")
    runtime.record_event(run.run_id, RuntimeEventType.AGENT_MESSAGE, {"message": "ok"})
    runtime.record_tool_result(run.run_id, "tool.name", {"ok": True}, {"x": 1})
    runtime.complete_run(run.run_id, output="done")

    events = runtime.list_events(run.run_id)
    assert [event.event_type for event in events][:2] == [
        RuntimeEventType.RUN_STARTED,
        RuntimeEventType.USER_INPUT_RECEIVED,
    ]
    assert RuntimeEventType.RUN_COMPLETED in [event.event_type for event in events]


def test_runtime_fail_and_unknown_run(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("hello")

    runtime.fail_run(run.run_id, "boom")
    assert runtime.storage.get_run(run.run_id).status is RunStatus.FAILED
    with pytest.raises(AilurosNotFoundError):
        runtime.record_event("run_missing", RuntimeEventType.AGENT_MESSAGE)
