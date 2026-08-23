from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ailuros.core.execution import (
    DecisionSummary,
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.models.common import Severity
from ailuros.signals import (
    RULE_VERSION,
    GovernanceSignal,
    SignalType,
    _make_signal_id,
    derive_signals,
)


def _make_projection(
    *,
    run_id: str = "run-test",
    lifecycle: Lifecycle = Lifecycle.COMPLETED,
    outcome: Outcome = Outcome.SUCCESS,
    validation: Validation = Validation.PASSED,
    scope: Scope = Scope.CLEAN,
    decisions: list[DecisionSummary] | None = None,
    evidence_refs: list[EvidenceRef] | None = None,
) -> ExecutionProjection:
    now = datetime.now(UTC)
    return ExecutionProjection(
        run_id=run_id,
        source="test",
        schema_version="1.0",
        lifecycle=lifecycle,
        outcome=outcome,
        validation=validation,
        scope=scope,
        started_at=now,
        completed_at=now + timedelta(hours=1),
        decisions=decisions or [],
        evidence_refs=evidence_refs or [],
        decision_count=len(decisions) if decisions else 0,
    )


# ── Signal model ────────────────────────────────────────────────────────


def test_governance_signal_build_returns_correct_shape() -> None:
    refs = [EvidenceRef(event_id="evt-1")]
    signal = GovernanceSignal.build(
        run_id="run-1",
        signal_type=SignalType.VALIDATION_FAILURE,
        severity=Severity.HIGH,
        subject="validation",
        details={"key": "value"},
        evidence_refs=refs,
    )
    assert signal.run_id == "run-1"
    assert signal.type == "validation_failure"
    assert signal.severity == "high"
    assert signal.subject == "validation"
    assert signal.details == {"key": "value"}
    assert signal.evidence_refs == refs
    assert signal.rule_version == RULE_VERSION
    assert isinstance(signal.signal_id, str)
    assert len(signal.signal_id) == 32
    assert isinstance(signal.created_at, datetime)


def test_signal_id_is_deterministic() -> None:
    refs = [EvidenceRef(event_id="evt-a")]
    id1 = _make_signal_id("run-x", "validation_failure", "validation", refs)
    id2 = _make_signal_id("run-x", "validation_failure", "validation", refs)
    assert id1 == id2


def test_signal_id_differs_by_run_id() -> None:
    refs = [EvidenceRef(event_id="evt-a")]
    id1 = _make_signal_id("run-1", "validation_failure", "validation", refs)
    id2 = _make_signal_id("run-2", "validation_failure", "validation", refs)
    assert id1 != id2


def test_signal_id_differs_by_type() -> None:
    refs = [EvidenceRef(event_id="evt-a")]
    id1 = _make_signal_id("run-1", "validation_failure", "validation", refs)
    id2 = _make_signal_id("run-1", "scope_violation", "validation", refs)
    assert id1 != id2


def test_signal_id_differs_by_evidence() -> None:
    refs_a = [EvidenceRef(event_id="evt-a")]
    refs_b = [EvidenceRef(event_id="evt-b")]
    id1 = _make_signal_id("run-1", "validation_failure", "validation", refs_a)
    id2 = _make_signal_id("run-1", "validation_failure", "validation", refs_b)
    assert id1 != id2


# ── Clean state: no signals ─────────────────────────────────────────────


def test_clean_projection_yields_no_signals() -> None:
    proj = _make_projection()
    signals = derive_signals(proj)
    assert signals == []


# ── Unknown state creates no fake clean signals ─────────────────────────


def test_unknown_state_creates_no_fake_clean_signals() -> None:
    proj = _make_projection(
        lifecycle=Lifecycle.UNKNOWN,
        outcome=Outcome.UNKNOWN,
        validation=Validation.UNKNOWN,
        scope=Scope.UNKNOWN,
    )
    signals = derive_signals(proj)
    assert signals == []


def test_unknown_validation_with_clean_outcome_yields_no_signals() -> None:
    proj = _make_projection(
        validation=Validation.UNKNOWN,
        outcome=Outcome.SUCCESS,
    )
    signals = derive_signals(proj)
    assert signals == []


# ── validation_failure ─────────────────────────────────────────────────


def test_validation_failure_signal() -> None:
    ref = EvidenceRef(event_id="evt-vf")
    proj = _make_projection(
        validation=Validation.FAILED,
        evidence_refs=[ref],
    )
    signals = derive_signals(proj)
    assert len(signals) == 1
    s = signals[0]
    assert s.type == SignalType.VALIDATION_FAILURE.value
    assert s.subject == "validation"
    assert s.severity == "high"
    assert s.details == {"validation": "failed"}
    assert s.evidence_refs == [ref]


def test_validation_passed_yields_no_validation_failure() -> None:
    proj = _make_projection(validation=Validation.PASSED)
    signals = derive_signals(proj)
    assert not any(s.type == "validation_failure" for s in signals)


def test_validation_partial_yields_no_validation_failure() -> None:
    proj = _make_projection(validation=Validation.PARTIAL)
    signals = derive_signals(proj)
    assert not any(s.type == "validation_failure" for s in signals)


# ── repeated_validation_failure ─────────────────────────────────────────


def test_repeated_validation_failure_signal() -> None:
    refs = [EvidenceRef(event_id="evt-1"), EvidenceRef(event_id="evt-2")]
    proj = _make_projection(
        validation=Validation.FAILED,
        decisions=[
            DecisionSummary(domain="bash", decision="block"),
            DecisionSummary(domain="write", decision="block"),
        ],
        evidence_refs=refs,
    )
    signals = derive_signals(proj)
    types = {s.type for s in signals}
    assert "repeated_validation_failure" in types
    rvf = next(s for s in signals if s.type == "repeated_validation_failure")
    assert rvf.severity == "high"
    assert rvf.details["failure_count"] == 2


def test_repeated_validation_failure_requires_two_or_more_blocks() -> None:
    proj = _make_projection(
        validation=Validation.FAILED,
        decisions=[DecisionSummary(domain="bash", decision="block")],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "repeated_validation_failure" for s in signals)


def test_repeated_validation_failure_ignores_audit_fail() -> None:
    proj = _make_projection(
        validation=Validation.FAILED,
        decisions=[
            DecisionSummary(domain="bash", decision="block"),
            DecisionSummary(domain="audit", decision="fail", projected_domain="post_run_audit"),
        ],
    )
    signals = derive_signals(proj)
    types = {s.type for s in signals}
    assert "repeated_validation_failure" not in types


# ── evidence_inconsistency ──────────────────────────────────────────────


def test_evidence_inconsistency_allow_and_block_same_domain() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(domain="bash", decision="allow"),
            DecisionSummary(domain="bash", decision="block"),
        ],
        evidence_refs=[EvidenceRef(event_id="evt-1")],
    )
    signals = derive_signals(proj)
    ei = [s for s in signals if s.type == "evidence_inconsistency"]
    assert len(ei) == 1
    assert ei[0].severity == "medium"
    assert len(ei[0].details["conflicts"]) == 1


def test_no_evidence_inconsistency_when_all_allow() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(domain="bash", decision="allow"),
            DecisionSummary(domain="read", decision="allow"),
        ],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "evidence_inconsistency" for s in signals)


def test_no_evidence_inconsistency_when_all_block() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(domain="bash", decision="block"),
            DecisionSummary(domain="write", decision="block"),
        ],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "evidence_inconsistency" for s in signals)


# ── evidence_inconsistency: scope-aware grouping ────────────────────────


def test_evidence_inconsistency_same_scope_and_domain_conflicts() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(
                domain="bash", decision="allow", scope_ref="scope-a"
            ),
            DecisionSummary(
                domain="bash", decision="block", scope_ref="scope-a"
            ),
        ],
        evidence_refs=[EvidenceRef(event_id="evt-1")],
    )
    signals = derive_signals(proj)
    ei = [s for s in signals if s.type == "evidence_inconsistency"]
    assert len(ei) == 1
    assert len(ei[0].details["conflicts"]) == 1
    conflict = ei[0].details["conflicts"][0]
    assert conflict["scope_ref"] == "scope-a"
    assert conflict["projected_domain"] == "source_preserved_unknown"


def test_no_evidence_inconsistency_across_different_scopes() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(
                domain="bash", decision="allow", scope_ref="scope-a"
            ),
            DecisionSummary(
                domain="bash", decision="block", scope_ref="scope-b"
            ),
        ],
        evidence_refs=[EvidenceRef(event_id="evt-1")],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "evidence_inconsistency" for s in signals)


def test_no_evidence_inconsistency_unscoped_vs_scoped() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(domain="bash", decision="allow"),
            DecisionSummary(
                domain="bash", decision="block", scope_ref="scope-a"
            ),
        ],
        evidence_refs=[EvidenceRef(event_id="evt-1")],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "evidence_inconsistency" for s in signals)


def test_evidence_inconsistency_unscoped_same_domain_still_conflicts() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(domain="bash", decision="allow"),
            DecisionSummary(domain="bash", decision="block"),
        ],
        evidence_refs=[EvidenceRef(event_id="evt-1")],
    )
    signals = derive_signals(proj)
    ei = [s for s in signals if s.type == "evidence_inconsistency"]
    assert len(ei) == 1
    assert len(ei[0].details["conflicts"]) == 1
    assert ei[0].details["conflicts"][0]["scope_ref"] is None


def test_evidence_inconsistency_conflict_is_isolated_per_scope() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(
                domain="bash", decision="allow", scope_ref="scope-a"
            ),
            DecisionSummary(
                domain="bash", decision="block", scope_ref="scope-a"
            ),
            DecisionSummary(
                domain="bash", decision="block", scope_ref="scope-b"
            ),
        ],
        evidence_refs=[EvidenceRef(event_id="evt-1")],
    )
    signals = derive_signals(proj)
    ei = [s for s in signals if s.type == "evidence_inconsistency"]
    assert len(ei) == 1
    assert len(ei[0].details["conflicts"]) == 1
    assert ei[0].details["conflicts"][0]["scope_ref"] == "scope-a"


# ── scope_violation ─────────────────────────────────────────────────────


def test_scope_violation_signal() -> None:
    ref = EvidenceRef(event_id="evt-sv")
    proj = _make_projection(scope=Scope.VIOLATED, evidence_refs=[ref])
    signals = derive_signals(proj)
    sv = [s for s in signals if s.type == "scope_violation"]
    assert len(sv) == 1
    assert sv[0].severity == "critical"
    assert sv[0].details == {"scope": "violated"}
    assert sv[0].evidence_refs == [ref]


def test_scope_clean_yields_no_scope_violation() -> None:
    proj = _make_projection(scope=Scope.CLEAN)
    signals = derive_signals(proj)
    assert not any(s.type == "scope_violation" for s in signals)


def test_scope_unknown_yields_no_scope_violation() -> None:
    proj = _make_projection(scope=Scope.UNKNOWN)
    signals = derive_signals(proj)
    assert not any(s.type == "scope_violation" for s in signals)


# ── forbidden_path_touched ──────────────────────────────────────────────


def test_forbidden_path_touched_signal() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(domain="path", decision="forbidden_path"),
        ],
        evidence_refs=[EvidenceRef(event_id="evt-fp")],
    )
    signals = derive_signals(proj)
    fp = [s for s in signals if s.type == "forbidden_path_touched"]
    assert len(fp) == 1
    assert fp[0].severity == "high"
    assert len(fp[0].details["triggering_decisions"]) == 1


def test_forbidden_path_via_domain_match() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(domain="forbidden_path_touched", decision="unknown"),
        ],
    )
    signals = derive_signals(proj)
    assert any(s.type == "forbidden_path_touched" for s in signals)


def test_no_forbidden_path_when_clean() -> None:
    proj = _make_projection(
        decisions=[DecisionSummary(domain="read", decision="allow")],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "forbidden_path_touched" for s in signals)


# ── backend_fallback ────────────────────────────────────────────────────


def test_backend_fallback_signal() -> None:
    proj = _make_projection(
        decisions=[DecisionSummary(domain="backend", decision="fallback")],
        evidence_refs=[EvidenceRef(event_id="evt-bf")],
    )
    signals = derive_signals(proj)
    bf = [s for s in signals if s.type == "backend_fallback"]
    assert len(bf) == 1
    assert bf[0].severity == "medium"


def test_backend_fallback_via_domain_match() -> None:
    proj = _make_projection(
        decisions=[DecisionSummary(domain="backend_fallback", decision="unknown")],
    )
    signals = derive_signals(proj)
    assert any(s.type == "backend_fallback" for s in signals)


def test_no_backend_fallback_when_clean() -> None:
    proj = _make_projection(
        decisions=[DecisionSummary(domain="backend", decision="available")],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "backend_fallback" for s in signals)


# ── backend_unavailable ─────────────────────────────────────────────────


def test_backend_unavailable_signal() -> None:
    proj = _make_projection(
        decisions=[DecisionSummary(domain="backend", decision="backend_unavailable")],
        evidence_refs=[EvidenceRef(event_id="evt-bu")],
    )
    signals = derive_signals(proj)
    bu = [s for s in signals if s.type == "backend_unavailable"]
    assert len(bu) == 1
    assert bu[0].severity == "high"


def test_no_backend_unavailable_when_clean() -> None:
    proj = _make_projection(
        decisions=[DecisionSummary(domain="backend", decision="available")],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "backend_unavailable" for s in signals)


# ── context_too_large ───────────────────────────────────────────────────


def test_context_too_large_signal() -> None:
    proj = _make_projection(
        decisions=[DecisionSummary(domain="context", decision="context_too_large")],
        evidence_refs=[EvidenceRef(event_id="evt-ct")],
    )
    signals = derive_signals(proj)
    ct = [s for s in signals if s.type == "context_too_large"]
    assert len(ct) == 1
    assert ct[0].severity == "low"


def test_context_too_large_via_token_limit() -> None:
    proj = _make_projection(
        decisions=[DecisionSummary(domain="context", decision="token_limit")],
    )
    signals = derive_signals(proj)
    assert any(s.type == "context_too_large" for s in signals)


def test_no_context_too_large_when_clean() -> None:
    proj = _make_projection(
        decisions=[DecisionSummary(domain="context", decision="ok")],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "context_too_large" for s in signals)


# ── coder_semantic_failure ──────────────────────────────────────────────


def test_coder_semantic_failure_signal() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(domain="coder", decision="coder_semantic_failure"),
        ],
        evidence_refs=[EvidenceRef(event_id="evt-cs")],
    )
    signals = derive_signals(proj)
    cs = [s for s in signals if s.type == "coder_semantic_failure"]
    assert len(cs) == 1
    assert cs[0].severity == "medium"


def test_coder_semantic_failure_only_from_explicit_decision() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(domain="coder", decision="block"),
        ],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "coder_semantic_failure" for s in signals)


def test_coder_semantic_failure_not_inferred_from_domain() -> None:
    proj = _make_projection(
        decisions=[
            DecisionSummary(domain="coder", decision="something_else"),
        ],
    )
    signals = derive_signals(proj)
    assert not any(s.type == "coder_semantic_failure" for s in signals)


# ── human_review_required ───────────────────────────────────────────────


def test_human_review_required_signal() -> None:
    ref = EvidenceRef(event_id="evt-hr")
    proj = _make_projection(
        outcome=Outcome.REVIEW_REQUIRED,
        evidence_refs=[ref],
    )
    signals = derive_signals(proj)
    hr = [s for s in signals if s.type == "human_review_required"]
    assert len(hr) == 1
    assert hr[0].severity == "medium"
    assert hr[0].details == {"outcome": "review_required"}
    assert hr[0].evidence_refs == [ref]


def test_human_review_required_not_fired_for_other_outcomes() -> None:
    for outcome in (Outcome.SUCCESS, Outcome.PARTIAL, Outcome.FAILED, Outcome.UNKNOWN):
        proj = _make_projection(outcome=outcome)
        signals = derive_signals(proj)
        assert not any(s.type == "human_review_required" for s in signals)


# ── Multiple signals from same projection ───────────────────────────────


def test_multiple_signals_can_fire_together() -> None:
    proj = _make_projection(
        validation=Validation.FAILED,
        scope=Scope.VIOLATED,
        outcome=Outcome.REVIEW_REQUIRED,
        decisions=[
            DecisionSummary(domain="bash", decision="block"),
            DecisionSummary(domain="read", decision="allow"),
        ],
        evidence_refs=[EvidenceRef(event_id="evt-1")],
    )
    signals = derive_signals(proj)
    types = {s.type for s in signals}
    assert "validation_failure" in types
    assert "scope_violation" in types
    assert "human_review_required" in types
    assert "evidence_inconsistency" in types


# ── Signal model serialization ──────────────────────────────────────────


def test_governance_signal_model_dump() -> None:
    signal = GovernanceSignal.build(
        run_id="run-1",
        signal_type=SignalType.SCOPE_VIOLATION,
        severity=Severity.CRITICAL,
        subject="scope",
        details={"key": "val"},
        evidence_refs=[EvidenceRef(event_id="evt-1", artifact="a.json")],
    )
    data = signal.model_dump(mode="json")
    assert data["run_id"] == "run-1"
    assert data["type"] == "scope_violation"
    assert data["severity"] == "critical"
    assert data["subject"] == "scope"
    assert data["details"] == {"key": "val"}
    assert data["rule_version"] == RULE_VERSION
    assert isinstance(data["signal_id"], str)
    assert isinstance(data["created_at"], str)
    assert data["evidence_refs"] == [
        {"event_id": "evt-1", "artifact": "a.json", "pointer": None}
    ]


# ── Edge cases ──────────────────────────────────────────────────────────


def test_empty_projection_yields_no_signals() -> None:
    now = datetime.now(UTC)
    proj = ExecutionProjection(
        run_id="minimal",
        source="test",
        schema_version="1.0",
        lifecycle=Lifecycle.RUNNING,
        outcome=Outcome.UNKNOWN,
        validation=Validation.NOT_RUN,
        scope=Scope.UNKNOWN,
        started_at=now,
    )
    signals = derive_signals(proj)
    assert signals == []


def test_all_enums_handled_gracefully() -> None:
    """No signal derivation should raise for any valid enum value."""
    now = datetime.now(UTC)
    for lifecycle in Lifecycle:
        for outcome in Outcome:
            for validation in Validation:
                for scope in Scope:
                    proj = ExecutionProjection(
                        run_id="all-enums",
                        source="test",
                        schema_version="1.0",
                        lifecycle=lifecycle,
                        outcome=outcome,
                        validation=validation,
                        scope=scope,
                        started_at=now,
                    )
                    result = derive_signals(proj)
                    assert isinstance(result, list)
                    for s in result:
                        assert isinstance(s, GovernanceSignal)
