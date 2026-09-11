from ailuros import AilurosRuntime, GovernanceDecisionType, RuntimeEventType

VALIDATION_ID = "validation-42"
VALIDATED_STATE_REF = "state-ref-validated-abc"
ACCEPTANCE_TARGET_REF = "state-ref-acceptance-xyz"
EVIDENCE_REFS = ["evidence/equivalence-1", "evidence/equivalence-2"]


def _runtime(tmp_path) -> AilurosRuntime:
    return AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")


def _use(runtime: AilurosRuntime, run_id: str, **overrides):
    facts = {
        "run_id": run_id,
        "validation_id": VALIDATION_ID,
        "validated_state_ref": VALIDATED_STATE_REF,
        "acceptance_target_ref": ACCEPTANCE_TARGET_REF,
        "state_equivalence": "confirmed",
        "evidence_refs": list(EVIDENCE_REFS),
    }
    facts.update(overrides)
    return runtime.before_validation_evidence_use(**facts)


def _event_types(runtime: AilurosRuntime, run_id: str) -> list[RuntimeEventType]:
    return [event.event_type for event in runtime.list_events(run_id)]


def test_confirmed_equivalence_with_evidence_allows(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("validation")

    decision = _use(runtime, run.run_id)

    assert decision.decision is GovernanceDecisionType.ALLOW
    assert decision.allowed is True


def test_violated_equivalence_with_evidence_blocks(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("validation")

    decision = _use(runtime, run.run_id, state_equivalence="violated")

    assert decision.decision is GovernanceDecisionType.BLOCK
    assert decision.allowed is False


def test_unknown_equivalence_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("validation")

    decision = _use(runtime, run.run_id, state_equivalence="unknown")

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_unrecognized_classification_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("validation")

    decision = _use(runtime, run.run_id, state_equivalence="kind-of-confirmed")

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_confirmed_equivalence_without_evidence_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("validation")

    decision = _use(runtime, run.run_id, evidence_refs=[])

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_violated_equivalence_without_evidence_requires_review(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("validation")

    decision = _use(runtime, run.run_id, state_equivalence="violated", evidence_refs=None)

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_request_precedes_governance_decision_and_preserves_facts(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("validation")

    decision = _use(runtime, run.run_id)

    events = runtime.list_events(run.run_id)
    types = [event.event_type for event in events]
    assert types.index(RuntimeEventType.VALIDATION_EVIDENCE_USE_REQUESTED) < types.index(
        RuntimeEventType.GOVERNANCE_DECISION
    )

    requested = next(
        event
        for event in events
        if event.event_type is RuntimeEventType.VALIDATION_EVIDENCE_USE_REQUESTED
    )
    assert requested.payload["validation_id"] == VALIDATION_ID
    assert requested.payload["validated_state_ref"] == VALIDATED_STATE_REF
    assert requested.payload["acceptance_target_ref"] == ACCEPTANCE_TARGET_REF
    assert requested.payload["state_equivalence"] == "confirmed"
    assert requested.payload["evidence_refs"] == EVIDENCE_REFS

    assert decision.metadata["governance_kind"] == "validation_evidence_use"
    assert decision.metadata["validation_id"] == VALIDATION_ID
    assert decision.metadata["validated_state_ref"] == VALIDATED_STATE_REF
    assert decision.metadata["acceptance_target_ref"] == ACCEPTANCE_TARGET_REF
    assert decision.metadata["state_equivalence"] == "confirmed"
    assert decision.metadata["evidence_refs"] == EVIDENCE_REFS
    assert decision.evidence_refs == EVIDENCE_REFS


def test_state_ref_equality_is_not_proof_of_equivalence(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("validation")

    same_ref = VALIDATED_STATE_REF
    decision = _use(
        runtime,
        run.run_id,
        validated_state_ref=same_ref,
        acceptance_target_ref=same_ref,
        state_equivalence="unknown",
    )

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.allowed is False


def test_different_state_refs_can_be_allow_when_evidence_confirms(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("validation")

    decision = _use(runtime, run.run_id)

    assert decision.decision is GovernanceDecisionType.ALLOW
    assert decision.allowed is True


def test_validation_evidence_gate_does_not_affect_tool_call_default_allow(tmp_path):
    runtime = _runtime(tmp_path)
    run = runtime.start_run("validation")
    _use(runtime, run.run_id)

    calls: list[int] = []

    def tool(value: int) -> int:
        calls.append(value)
        return value

    result = runtime.wrap_tool("unrelated.tool", tool)(run_id=run.run_id, value=1)

    assert result.blocked is False
    assert result.decision.decision is GovernanceDecisionType.ALLOW
    assert calls == [1]
