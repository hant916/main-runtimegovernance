from __future__ import annotations

from datetime import UTC, datetime

from ailuros.core.execution import GovernanceContext, GovernanceContextConflict
from ailuros.projection import build_execution_projection


def _event(
    event_type: str,
    *,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    payload: dict | None = None,
    step_id: str | None = None,
) -> dict:
    ts = timestamp or datetime.now(UTC)
    eid = event_id or f"evt-{event_type}"
    return {
        "event_id": eid,
        "event_type": event_type,
        "timestamp": ts,
        "payload": payload or {},
        "step_id": step_id,
    }


def _context_event(
    event_id: str,
    *,
    principal_ref: str | None = None,
    workflow_ref: str | None = None,
    invocation_ref: str | None = None,
    policy_snapshot_ref: str | None = None,
    source_pointers: list[str] | None = None,
) -> dict:
    payload: dict = {}
    if principal_ref is not None:
        payload["principal_ref"] = principal_ref
    if workflow_ref is not None:
        payload["workflow_ref"] = workflow_ref
    if invocation_ref is not None:
        payload["invocation_ref"] = invocation_ref
    if policy_snapshot_ref is not None:
        payload["policy_snapshot_ref"] = policy_snapshot_ref
    if source_pointers is not None:
        payload["source_pointers"] = source_pointers
    return _event("governance_context", event_id=event_id, payload=payload)


# ── T1: Model defaults ──────────────────────────────────────────────────


def test_governance_context_defaults() -> None:
    ctx = GovernanceContext()
    assert ctx.principal_ref is None
    assert ctx.workflow_ref is None
    assert ctx.invocation_ref is None
    assert ctx.policy_snapshot_ref is None
    assert ctx.source_pointers == []
    assert ctx.inconsistencies == []


def test_governance_context_conflict_model() -> None:
    conflict = GovernanceContextConflict(
        field="principal_ref",
        values=["user:alice", "user:bob"],
        source_pointers=["e1", "e2"],
    )
    assert conflict.field == "principal_ref"
    assert conflict.values == ["user:alice", "user:bob"]
    assert conflict.source_pointers == ["e1", "e2"]


# ── T2: Absent context remains None ─────────────────────────────────────


def test_no_context_events_yields_none() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("run_completed", event_id="e2"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.governance_context is None


def test_context_event_with_empty_payload_yields_none() -> None:
    events = [
        _event("governance_context", event_id="e1", payload={}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.governance_context is None


# ── T3: Explicit evidence is mapped ─────────────────────────────────────


def test_explicit_context_fields_projected() -> None:
    events = [
        _context_event(
            "e1",
            principal_ref="user:alice",
            workflow_ref="task:8032",
            invocation_ref="inv:abc123",
            policy_snapshot_ref="sha256:9f2c",
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ctx = proj.governance_context
    assert ctx is not None
    assert ctx.principal_ref == "user:alice"
    assert ctx.workflow_ref == "task:8032"
    assert ctx.invocation_ref == "inv:abc123"
    assert ctx.policy_snapshot_ref == "sha256:9f2c"
    assert ctx.inconsistencies == []


def test_source_pointers_retained() -> None:
    events = [
        _context_event(
            "e1",
            principal_ref="user:alice",
            source_pointers=["evt-001", "evt-014"],
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ctx = proj.governance_context
    assert ctx is not None
    assert ctx.source_pointers == ["e1", "evt-001", "evt-014"]


def test_context_event_appears_in_evidence_refs() -> None:
    events = [
        _context_event("e1", principal_ref="user:alice"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ref_ids = {r.event_id for r in proj.evidence_refs}
    assert "e1" in ref_ids


def test_partial_context_leaves_other_fields_none() -> None:
    events = [
        _context_event("e1", principal_ref="user:alice"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ctx = proj.governance_context
    assert ctx is not None
    assert ctx.principal_ref == "user:alice"
    assert ctx.workflow_ref is None
    assert ctx.invocation_ref is None
    assert ctx.policy_snapshot_ref is None


def test_identical_repeated_values_are_not_a_conflict() -> None:
    events = [
        _context_event("e1", principal_ref="user:alice"),
        _context_event("e2", principal_ref="user:alice"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ctx = proj.governance_context
    assert ctx is not None
    assert ctx.principal_ref == "user:alice"
    assert ctx.inconsistencies == []


# ── T4: Conflicting explicit values are preserved as inconsistency ──────


def test_conflicting_principal_ref_yields_inconsistency() -> None:
    events = [
        _context_event("e1", principal_ref="user:alice"),
        _context_event("e2", principal_ref="user:bob"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ctx = proj.governance_context
    assert ctx is not None
    assert ctx.principal_ref is None
    assert len(ctx.inconsistencies) == 1
    conflict = ctx.inconsistencies[0]
    assert conflict.field == "principal_ref"
    assert conflict.values == ["user:alice", "user:bob"]
    assert conflict.source_pointers == ["e1", "e2"]


def test_conflict_does_not_last_write_win() -> None:
    events = [
        _context_event("e1", workflow_ref="task:A"),
        _context_event("e2", workflow_ref="task:B"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ctx = proj.governance_context
    assert ctx is not None
    assert ctx.workflow_ref is None
    assert len(ctx.inconsistencies) == 1


def test_multiple_conflicts_preserved_independently() -> None:
    events = [
        _context_event("e1", principal_ref="user:alice", invocation_ref="inv:a"),
        _context_event("e2", principal_ref="user:bob", invocation_ref="inv:b"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ctx = proj.governance_context
    assert ctx is not None
    assert ctx.principal_ref is None
    assert ctx.invocation_ref is None
    conflict_fields = {c.field for c in ctx.inconsistencies}
    assert conflict_fields == {"principal_ref", "invocation_ref"}


def test_non_conflicting_fields_keep_their_value_during_conflict() -> None:
    events = [
        _context_event("e1", principal_ref="user:alice", workflow_ref="task:8032"),
        _context_event("e2", principal_ref="user:bob", workflow_ref="task:8032"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ctx = proj.governance_context
    assert ctx is not None
    assert ctx.principal_ref is None
    assert ctx.workflow_ref == "task:8032"
    assert len(ctx.inconsistencies) == 1


# ── T5: No inference from backend/model/role or run_id ──────────────────


def test_principal_not_inferred_from_role_or_backend() -> None:
    events = [
        _event(
            "runtime_role",
            event_id="e1",
            payload={"name": "coder", "backend": "openai", "model": "gpt-4"},
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.governance_context is None


def test_workflow_not_inferred_from_run_id() -> None:
    events = [
        _event("run_started", event_id="e1"),
    ]
    proj = build_execution_projection("task:9999", "test", events)
    assert proj.governance_context is None


def test_non_string_refs_ignored() -> None:
    events = [
        _event(
            "governance_context",
            event_id="e1",
            payload={"principal_ref": 123, "workflow_ref": ""},
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.governance_context is None


# ── T6: Source neutrality ───────────────────────────────────────────────


def test_everrun_like_fixture_projects_context() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _context_event(
            "e2",
            principal_ref="user:alice",
            workflow_ref="task:8033",
            invocation_ref="inv:abc",
            policy_snapshot_ref="sha256:policy-1",
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-everrun", "everrun", events)
    ctx = proj.governance_context
    assert ctx is not None
    assert ctx.principal_ref == "user:alice"
    assert ctx.workflow_ref == "task:8033"
    assert ctx.invocation_ref == "inv:abc"
    assert ctx.policy_snapshot_ref == "sha256:policy-1"


def test_generic_second_producer_fixture_projects_same_context() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _context_event(
            "e2",
            principal_ref="user:alice",
            workflow_ref="task:8033",
            invocation_ref="inv:abc",
            policy_snapshot_ref="sha256:policy-1",
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-clarify", "clarify", events)
    ctx = proj.governance_context
    assert ctx is not None
    assert ctx.principal_ref == "user:alice"
    assert ctx.workflow_ref == "task:8033"


def test_core_does_not_branch_on_producer_name() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _context_event(
            "e2",
            principal_ref="user:alice",
            workflow_ref="task:8033",
            invocation_ref="inv:abc",
            policy_snapshot_ref="sha256:policy-1",
        ),
        _event("run_completed", event_id="e3"),
    ]
    everrun = build_execution_projection("run-everrun", "everrun", events)
    clarify = build_execution_projection("run-clarify", "clarify", events)

    assert everrun.governance_context is not None
    assert clarify.governance_context is not None
    assert everrun.governance_context == clarify.governance_context
    assert everrun.source == "everrun"
    assert clarify.source == "clarify"
