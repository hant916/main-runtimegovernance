from ailuros import AilurosRuntime, GovernanceDecisionType, RuntimeEventType

ACTION_REF = "action/coder-1"
OUTCOME_REF = "outcome/digest-2"
EVIDENCE_REFS = ["evidence/consistency-1"]


def _runtime(tmp_path) -> AilurosRuntime:
    return AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")


def _use(runtime: AilurosRuntime, run_id: str, **overrides):
    facts = {
        "run_id": run_id,
        "action_ref": ACTION_REF,
        "outcome_ref": OUTCOME_REF,
        "consistency": "confirmed",
        "evidence_refs": list(EVIDENCE_REFS),
    }
    facts.update(overrides)
    return runtime.before_action_outcome_use(**facts)


def test_confirmed_consistency_with_evidence_allows(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("outcome")

    decision = _use(runtime, run.run_id)

    assert decision.decision is GovernanceDecisionType.ALLOW
    assert decision.allowed is True


def test_violated_consistency_with_evidence_blocks(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("outcome")

    decision = _use(runtime, run.run_id, consistency="violated")

    assert decision.decision is GovernanceDecisionType.BLOCK
    assert decision.allowed is False


def test_unknown_consistency_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("outcome")

    decision = _use(runtime, run.run_id, consistency="unknown")

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_unrecognized_consistency_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("outcome")

    decision = _use(runtime, run.run_id, consistency="kind-of-consistent")

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_confirmed_or_violated_without_evidence_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("outcome")

    confirmed = _use(runtime, run.run_id, evidence_refs=[])
    violated = _use(
        runtime, run.run_id, consistency="violated", evidence_refs=None
    )

    assert confirmed.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert confirmed.allowed is False
    assert violated.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert violated.allowed is False


def test_request_precedes_decision_and_preserves_outcome_facts(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("outcome")

    decision = _use(runtime, run.run_id, metadata={"consumer": "downstream"})

    events = runtime.list_events(run.run_id)
    types = [event.event_type for event in events]
    assert types.index(RuntimeEventType.ACTION_OUTCOME_USE_REQUESTED) < types.index(
        RuntimeEventType.GOVERNANCE_DECISION
    )
    requested = next(
        event
        for event in events
        if event.event_type is RuntimeEventType.ACTION_OUTCOME_USE_REQUESTED
    )
    assert requested.payload == {
        "action_ref": ACTION_REF,
        "outcome_ref": OUTCOME_REF,
        "consistency": "confirmed",
        "evidence_refs": EVIDENCE_REFS,
        "metadata": {"consumer": "downstream"},
    }
    assert decision.metadata["governance_kind"] == "action_outcome_use"
    assert decision.metadata["action_ref"] == ACTION_REF
    assert decision.metadata["outcome_ref"] == OUTCOME_REF
    assert decision.metadata["consistency"] == "confirmed"
    assert decision.metadata["evidence_refs"] == EVIDENCE_REFS
    assert decision.evidence_refs == EVIDENCE_REFS
    assert decision.input_hash is not None and len(decision.input_hash) == 64


def test_outcome_gate_does_not_affect_tool_call_default_allow(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("outcome")
    _use(runtime, run.run_id)

    calls: list[int] = []

    def tool(value: int) -> int:
        calls.append(value)
        return value

    result = runtime.wrap_tool("unrelated.tool", tool)(run_id=run.run_id, value=1)

    assert result.blocked is False
    assert result.decision.decision is GovernanceDecisionType.ALLOW
    assert calls == [1]
