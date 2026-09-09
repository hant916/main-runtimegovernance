from ailuros import AilurosRuntime, GovernanceDecisionType, RuntimeEventType

ROLE = "planner"
FROM_IDENTITY = "codex/default"
TO_IDENTITY = "opencode/deepseek/deepseek-v4-pro"
REASON = "fresh_unavailable"
AUTHORITY_LEVEL = "terminal_decision"


def _policy_json(policy_id: str, decision: str) -> str:
    return f'''{{
      "policy_id": "{policy_id}",
      "version": "1",
      "decision": "{decision}",
      "severity": "critical",
      "match": {{
        "role": "{ROLE}",
        "from_identity": "{FROM_IDENTITY}",
        "to_identity": "{TO_IDENTITY}",
        "reason": "{REASON}",
        "authority_level": "{AUTHORITY_LEVEL}"
      }}
    }}'''


def _runtime_with_policy(tmp_path, policy_id: str, decision: str) -> AilurosRuntime:
    policy = tmp_path / f"{policy_id}.json"
    policy.write_text(_policy_json(policy_id, decision))
    return AilurosRuntime(storage_path=tmp_path / "runtime.sqlite", policies=[policy])


def _event_types(runtime: AilurosRuntime, run_id: str) -> list[RuntimeEventType]:
    return [event.event_type for event in runtime.list_events(run_id)]


def _substitute(runtime: AilurosRuntime, run_id: str):
    return runtime.before_actor_substitution(
        run_id,
        role=ROLE,
        from_identity=FROM_IDENTITY,
        to_identity=TO_IDENTITY,
        reason=REASON,
        authority_level=AUTHORITY_LEVEL,
    )


def test_exact_preauthorization_policy_allows_substitution(tmp_path):
    runtime = _runtime_with_policy(tmp_path, "allow.substitution", "allow")
    run = runtime.start_run("substitution")

    decision = _substitute(runtime, run.run_id)

    assert decision.decision is GovernanceDecisionType.ALLOW
    assert decision.allowed is True


def test_no_matching_policy_requires_review_not_allow(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("substitution")

    decision = _substitute(runtime, run.run_id)

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_explicit_block_policy_blocks_substitution(tmp_path):
    runtime = _runtime_with_policy(tmp_path, "block.substitution", "block")
    run = runtime.start_run("substitution")

    decision = _substitute(runtime, run.run_id)

    assert decision.decision is GovernanceDecisionType.BLOCK
    assert decision.allowed is False


def test_warn_policy_does_not_authorize_substitution(tmp_path):
    runtime = _runtime_with_policy(tmp_path, "warn.substitution", "warn")
    run = runtime.start_run("substitution")

    decision = _substitute(runtime, run.run_id)

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_sanitize_policy_does_not_authorize_substitution(tmp_path):
    runtime = _runtime_with_policy(tmp_path, "sanitize.substitution", "sanitize")
    run = runtime.start_run("substitution")

    decision = _substitute(runtime, run.run_id)

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_requested_event_precedes_governance_decision_with_structured_identities(tmp_path):
    runtime = _runtime_with_policy(tmp_path, "allow.substitution", "allow")
    run = runtime.start_run("substitution")

    decision = _substitute(runtime, run.run_id)

    events = runtime.list_events(run.run_id)
    types = [event.event_type for event in events]
    assert types.index(RuntimeEventType.ACTOR_SUBSTITUTION_REQUESTED) < types.index(
        RuntimeEventType.GOVERNANCE_DECISION
    )

    requested = next(
        event
        for event in events
        if event.event_type is RuntimeEventType.ACTOR_SUBSTITUTION_REQUESTED
    )
    assert requested.payload["role"] == ROLE
    assert requested.payload["from_identity"] == FROM_IDENTITY
    assert requested.payload["to_identity"] == TO_IDENTITY
    assert requested.payload["reason"] == REASON
    assert requested.payload["authority_level"] == AUTHORITY_LEVEL

    assert decision.metadata["governance_kind"] == "actor_substitution"
    assert decision.metadata["role"] == ROLE
    assert decision.metadata["from_identity"] == FROM_IDENTITY
    assert decision.metadata["to_identity"] == TO_IDENTITY
    assert decision.input_hash is not None


def test_actor_substitution_does_not_affect_tool_call_default_allow(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("substitution")
    _substitute(runtime, run.run_id)

    calls: list[int] = []

    def tool(value: int) -> int:
        calls.append(value)
        return value

    result = runtime.wrap_tool("unrelated.tool", tool)(run_id=run.run_id, value=1)

    assert result.blocked is False
    assert result.decision.decision is GovernanceDecisionType.ALLOW
    assert calls == [1]


def test_actor_substitution_policy_does_not_match_tool_call(tmp_path):
    runtime = _runtime_with_policy(tmp_path, "block.substitution", "block")
    run = runtime.start_run("substitution")

    calls: list[int] = []
    result = runtime.wrap_tool("some.tool", lambda: calls.append(1))(run_id=run.run_id)

    assert result.blocked is False
    assert result.decision.decision is GovernanceDecisionType.ALLOW
    assert calls == [1]
