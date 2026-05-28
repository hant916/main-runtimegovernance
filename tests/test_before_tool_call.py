import json
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


def test_before_tool_call_requires_previous_steps_met(tmp_path):
    policy_json = {
        "policy_id": "require_run_started",
        "version": "1",
        "decision": "require_review",
        "severity": "high",
        "match": {"tool_name": "test_tool"},
        "requires_previous_steps": {"prior_events.0.event_type": {"eq": "run_started"}},
    }
    policy_file = tmp_path / "require_run_started.json"
    policy_file.write_text(json.dumps(policy_json))

    runtime = AilurosRuntime(
        storage_path=tmp_path / "runtime.sqlite",
        policies=[policy_file],
    )
    run = runtime.start_run("test")
    decision = runtime.before_tool_call(run.run_id, "test_tool", {})
    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert not decision.allowed


def test_before_tool_call_requires_previous_steps_unmet(tmp_path):
    policy_json = {
        "policy_id": "require_prior_executed",
        "version": "1",
        "decision": "require_review",
        "severity": "high",
        "match": {"tool_name": "test_tool"},
        "requires_previous_steps": {
            "prior_events.2.event_type": {"eq": "tool_call_executed"}
        },
    }
    policy_file = tmp_path / "require_prior_executed.json"
    policy_file.write_text(json.dumps(policy_json))

    runtime = AilurosRuntime(
        storage_path=tmp_path / "runtime.sqlite",
        policies=[policy_file],
    )
    run = runtime.start_run("test")
    decision = runtime.before_tool_call(run.run_id, "test_tool", {})
    assert decision.decision is GovernanceDecisionType.ALLOW
    assert decision.allowed
