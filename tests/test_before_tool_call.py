from pathlib import Path

from ailuros import AilurosRuntime, GovernanceDecisionType, RuntimeEventType


def test_before_tool_call_allows_when_no_policy(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("hello")

    decision = runtime.before_tool_call(run.run_id, "payment.issue_refund", {"amount_eur": 1})

    assert decision.decision is GovernanceDecisionType.ALLOW
    assert decision.allowed


def test_before_tool_call_requires_review_and_persists_events(tmp_path):
    runtime = AilurosRuntime(
        storage_path=tmp_path / "runtime.sqlite",
        policies=[Path("tests/policy/fixtures/valid_refund_policy.json")],
    )
    run = runtime.start_run("refund")

    decision = runtime.before_tool_call(
        run.run_id, "payment.issue_refund", {"amount_eur": 780}
    )
    event_types = [event.event_type for event in runtime.list_events(run.run_id)]

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert not decision.allowed
    assert RuntimeEventType.TOOL_CALL_REQUESTED in event_types
    assert RuntimeEventType.POLICY_EVALUATION_RESULT in event_types
    assert RuntimeEventType.GOVERNANCE_DECISION in event_types
    assert RuntimeEventType.TOOL_CALL_BLOCKED in event_types
