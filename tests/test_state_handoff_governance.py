from ailuros import AilurosRuntime, GovernanceDecisionType, RuntimeEventType

SOURCE_EXECUTION_REF = "execution/source-123"
TARGET_EXECUTION_REF = "execution/target-456"
STATE_REF = "state/checkpoint-789"
EVIDENCE_REFS = ["evidence/state-assurance-1"]


def _runtime(tmp_path) -> AilurosRuntime:
    return AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")


def _handoff(runtime: AilurosRuntime, run_id: str, **overrides):
    facts = {
        "run_id": run_id,
        "source_execution_ref": SOURCE_EXECUTION_REF,
        "target_execution_ref": TARGET_EXECUTION_REF,
        "state_ref": STATE_REF,
        "state_assurance": "accepted",
        "evidence_refs": list(EVIDENCE_REFS),
    }
    facts.update(overrides)
    return runtime.before_state_handoff(**facts)


def test_accepted_state_assurance_with_evidence_allows(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("handoff")

    decision = _handoff(runtime, run.run_id)

    assert decision.decision is GovernanceDecisionType.ALLOW
    assert decision.allowed is True


def test_rejected_state_assurance_with_evidence_blocks(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("handoff")

    decision = _handoff(runtime, run.run_id, state_assurance="rejected")

    assert decision.decision is GovernanceDecisionType.BLOCK
    assert decision.allowed is False


def test_unverified_state_assurance_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("handoff")

    decision = _handoff(runtime, run.run_id, state_assurance="unverified")

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_unknown_state_assurance_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("handoff")

    decision = _handoff(runtime, run.run_id, state_assurance="unknown")

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_unrecognized_state_assurance_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("handoff")

    decision = _handoff(runtime, run.run_id, state_assurance="kind-of-accepted")

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_accepted_or_rejected_assurance_without_evidence_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("handoff")

    accepted = _handoff(runtime, run.run_id, evidence_refs=[])
    rejected = _handoff(
        runtime, run.run_id, state_assurance="rejected", evidence_refs=None
    )

    assert accepted.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert accepted.allowed is False
    assert rejected.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert rejected.allowed is False


def test_request_precedes_decision_and_preserves_handoff_facts(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("handoff")

    decision = _handoff(runtime, run.run_id, metadata={"requester": "external-runtime"})

    events = runtime.list_events(run.run_id)
    types = [event.event_type for event in events]
    assert types.index(RuntimeEventType.STATE_HANDOFF_REQUESTED) < types.index(
        RuntimeEventType.GOVERNANCE_DECISION
    )
    requested = next(
        event for event in events if event.event_type is RuntimeEventType.STATE_HANDOFF_REQUESTED
    )
    assert requested.payload == {
        "source_execution_ref": SOURCE_EXECUTION_REF,
        "target_execution_ref": TARGET_EXECUTION_REF,
        "state_ref": STATE_REF,
        "state_assurance": "accepted",
        "evidence_refs": EVIDENCE_REFS,
        "metadata": {"requester": "external-runtime"},
    }
    assert decision.metadata["governance_kind"] == "state_handoff"
    assert decision.metadata["state_ref"] == STATE_REF
    assert decision.metadata["state_assurance"] == "accepted"
    assert decision.metadata["evidence_refs"] == EVIDENCE_REFS
    assert decision.evidence_refs == EVIDENCE_REFS
    assert decision.input_hash is not None and len(decision.input_hash) == 64


def test_reference_equality_is_not_used_to_infer_state_assurance(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("handoff")

    decision = _handoff(
        runtime,
        run.run_id,
        source_execution_ref=SOURCE_EXECUTION_REF,
        target_execution_ref=SOURCE_EXECUTION_REF,
        state_ref=SOURCE_EXECUTION_REF,
        state_assurance="unknown",
    )

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_state_handoff_gate_does_not_affect_tool_call_default_allow(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("handoff")
    _handoff(runtime, run.run_id)

    calls: list[int] = []

    def tool(value: int) -> int:
        calls.append(value)
        return value

    result = runtime.wrap_tool("unrelated.tool", tool)(run_id=run.run_id, value=1)

    assert result.blocked is False
    assert result.decision.decision is GovernanceDecisionType.ALLOW
    assert calls == [1]
