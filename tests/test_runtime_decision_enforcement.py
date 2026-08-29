from ailuros import AilurosRuntime, GovernanceDecisionType, RuntimeEventType


def _runtime_with_policy(tmp_path, decision: str) -> AilurosRuntime:
    policy = tmp_path / f"{decision}.json"
    policy.write_text(
        f'''{{
          "policy_id": "{decision}.tool",
          "version": "1",
          "decision": "{decision}",
          "severity": "critical",
          "match": {{"tool_name": "governed.tool"}}
        }}'''
    )
    return AilurosRuntime(storage_path=tmp_path / "runtime.sqlite", policies=[policy])


def _event_types(runtime: AilurosRuntime, run_id: str) -> list[RuntimeEventType]:
    return [event.event_type for event in runtime.list_events(run_id)]


def test_allow_decision_precedes_single_execution_and_records_outcome(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("allow")
    calls: list[int] = []

    def tool(value: int) -> int:
        calls.append(value)
        return value + 1

    result = runtime.wrap_tool("governed.tool", tool)(run_id=run.run_id, value=2)

    assert result.blocked is False
    assert result.decision.decision is GovernanceDecisionType.ALLOW
    assert result.result == 3
    assert calls == [2]
    events = _event_types(runtime, run.run_id)
    assert events.index(RuntimeEventType.GOVERNANCE_DECISION) < events.index(
        RuntimeEventType.TOOL_CALL_EXECUTED
    )
    assert events.count(RuntimeEventType.TOOL_CALL_EXECUTED) == 1
    assert events.count(RuntimeEventType.TOOL_RESULT_RECEIVED) == 1


def test_block_decision_records_non_execution_without_calling_tool(tmp_path):
    runtime = _runtime_with_policy(tmp_path, "block")
    run = runtime.start_run("block")
    calls: list[None] = []

    result = runtime.wrap_tool("governed.tool", lambda: calls.append(None))(run_id=run.run_id)

    assert result.blocked is True
    assert result.decision.decision is GovernanceDecisionType.BLOCK
    assert calls == []
    events = runtime.list_events(run.run_id)
    assert RuntimeEventType.TOOL_CALL_EXECUTED not in _event_types(runtime, run.run_id)
    blocked = [event for event in events if event.event_type is RuntimeEventType.TOOL_CALL_BLOCKED]
    assert len(blocked) == 1
    assert blocked[0].payload["decision"] == GovernanceDecisionType.BLOCK.value


def test_review_decision_records_pending_governance_without_calling_tool(tmp_path):
    runtime = _runtime_with_policy(tmp_path, "require_review")
    run = runtime.start_run("review")
    calls: list[None] = []

    result = runtime.wrap_tool("governed.tool", lambda: calls.append(None))(run_id=run.run_id)

    assert result.blocked is True
    assert result.decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert calls == []
    events = runtime.list_events(run.run_id)
    assert RuntimeEventType.TOOL_CALL_EXECUTED not in _event_types(runtime, run.run_id)
    blocked = [event for event in events if event.event_type is RuntimeEventType.TOOL_CALL_BLOCKED]
    assert len(blocked) == 1
    assert blocked[0].payload["decision"] == GovernanceDecisionType.REQUIRE_REVIEW.value


def test_read_only_event_view_does_not_recompute_policy_or_invoke_tools(tmp_path, monkeypatch):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("readonly")
    tool_calls: list[None] = []
    runtime.wrap_tool("governed.tool", lambda: tool_calls.append(None))
    runtime.before_tool_call(run.run_id, "governed.tool")

    monkeypatch.setattr(
        runtime.policy_engine,
        "evaluate_tool_call",
        lambda _context: (_ for _ in ()).throw(AssertionError("policy recomputed")),
    )
    replayed = runtime.list_events(run.run_id)

    assert replayed
    assert tool_calls == []
