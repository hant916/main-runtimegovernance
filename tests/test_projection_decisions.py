from __future__ import annotations

from datetime import UTC, datetime

from ailuros.core.execution import Outcome
from ailuros.projection import _project_decision_domain, build_execution_projection


def _event(
    event_type: str,
    *,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    payload: dict | None = None,
    step_id: str | None = None,
    scope_ref: str | None = None,
) -> dict:
    ts = timestamp or datetime.now(UTC)
    eid = event_id or f"evt-{event_type}"
    event = {
        "event_id": eid,
        "event_type": event_type,
        "timestamp": ts,
        "payload": payload or {},
        "step_id": step_id,
    }
    if scope_ref is not None:
        event["scope_ref"] = scope_ref
    return event


# ── T1: Recognize explicit domains ─────────────────────────────────────


def test_tool_name_maps_to_runtime_action() -> None:
    assert _project_decision_domain({"tool_name": "read"}, "allow") == "runtime_action"


def test_tool_name_present_always_yields_runtime_action() -> None:
    assert _project_decision_domain(
        {"tool_name": "bash", "domain": "something_else"}, "block"
    ) == "runtime_action"


def test_explicit_execution_control_domain() -> None:
    assert _project_decision_domain(
        {"domain": "execution_control"}, "block"
    ) == "execution_control"


def test_explicit_post_run_audit_domain() -> None:
    assert _project_decision_domain(
        {"domain": "post_run_audit"}, "pass"
    ) == "post_run_audit"


def test_audit_decision_values_map_to_post_run_audit() -> None:
    assert _project_decision_domain({}, "pass") == "post_run_audit"
    assert _project_decision_domain({}, "warn") == "post_run_audit"
    assert _project_decision_domain({}, "fail") == "post_run_audit"


def test_unknown_domain_remains_source_preserved_unknown() -> None:
    assert _project_decision_domain({}, "allow") == "source_preserved_unknown"
    assert (
        _project_decision_domain({"domain": "custom"}, "custom_action")
        == "source_preserved_unknown"
    )


def test_runtime_action_in_projection() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert len(proj.decisions) == 1
    assert proj.decisions[0].projected_domain == "runtime_action"


def test_execution_control_in_projection() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "domain": "execution_control"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.decisions[0].projected_domain == "execution_control"


def test_post_run_audit_in_projection() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "fail"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.decisions[0].projected_domain == "post_run_audit"


def test_source_preserved_unknown_in_projection() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "unknown_decision"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.decisions[0].projected_domain == "source_preserved_unknown"


# ── T2: Preserve source value ──────────────────────────────────────────


def test_native_decision_stored_verbatim() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "CUSTOM_VALUE", "tool_name": "bash"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.decisions[0].decision == "CUSTOM_VALUE"


def test_native_domain_stored_verbatim() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.decisions[0].domain == "bash"


def test_projected_domain_does_not_replace_native_values() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "pass", "domain": "custom_domain"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    d = proj.decisions[0]
    assert d.domain == "custom_domain"
    assert d.decision == "pass"
    assert d.projected_domain == "post_run_audit"
    assert d.projected_domain != d.domain


def test_projected_domain_coexists_with_native_values() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "allow", "tool_name": "read"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    d = proj.decisions[0]
    assert d.domain == "read"
    assert d.decision == "allow"
    assert d.projected_domain == "runtime_action"
    assert hasattr(d, "projected_domain")


def test_multiple_decisions_each_preserve_their_source() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event(
            "governance_decision",
            event_id="e3",
            payload={"decision": "warn", "tool_name": "write"},
        ),
        _event("run_completed", event_id="e4"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.decisions[0].domain == "bash"
    assert proj.decisions[0].decision == "block"
    assert proj.decisions[0].projected_domain == "runtime_action"
    assert proj.decisions[1].domain == "write"
    assert proj.decisions[1].decision == "warn"
    assert proj.decisions[1].projected_domain == "runtime_action"


# ── T3: Preserve reason/applied rules as details ───────────────────────


def test_evidence_refs_point_to_decision_event() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="decision-evt",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    decision_refs = [
        r for r in proj.evidence_refs if r.event_id == "decision-evt"
    ]
    assert len(decision_refs) == 1


def test_no_synthesized_reason_in_decision_summary() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    d = proj.decisions[0]
    assert not hasattr(d, "reason")
    assert not hasattr(d, "rules")


def test_multiple_decision_evidence_refs_preserved() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "allow", "tool_name": "read"},
        ),
        _event(
            "governance_decision",
            event_id="e3",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed", event_id="e4"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    decision_event_ids = {r.event_id for r in proj.evidence_refs if r.event_id in ("e2", "e3")}
    assert decision_event_ids == {"e2", "e3"}


# ── T4: Same-word ambiguity ────────────────────────────────────────────


def test_block_in_runtime_action_distinct_from_outcome() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.BLOCKED
    d = proj.decisions[0]
    assert d.decision == "block"
    assert d.projected_domain == "runtime_action"
    assert d.projected_domain != "block"


def test_block_in_execution_control_is_distinct_domain() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "domain": "execution_control"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.decisions[0].projected_domain == "execution_control"
    assert proj.decisions[0].projected_domain != "runtime_action"


def test_pass_decision_remains_audit_domain() -> None:
    assert _project_decision_domain({}, "pass") == "post_run_audit"


def test_warn_decision_remains_audit_domain() -> None:
    assert _project_decision_domain({}, "warn") == "post_run_audit"


def test_fail_decision_remains_audit_domain() -> None:
    assert _project_decision_domain({}, "fail") == "post_run_audit"


def test_warn_with_tool_name_is_runtime_action_not_audit() -> None:
    assert _project_decision_domain(
        {"tool_name": "exec"}, "warn"
    ) == "runtime_action"


def test_runtime_block_and_audit_fail_are_different_domains() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event(
            "governance_decision",
            event_id="e3",
            payload={"decision": "fail"},
        ),
        _event("run_completed", event_id="e4"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.decisions[0].projected_domain == "runtime_action"
    assert proj.decisions[1].projected_domain == "post_run_audit"
    assert proj.decisions[0].projected_domain != proj.decisions[1].projected_domain


# ── Default value for DecisionSummary.projected_domain ─────────────────


def test_decision_summary_default_projected_domain() -> None:
    from ailuros.core.execution import DecisionSummary

    d = DecisionSummary(domain="test", decision="allow")
    assert d.projected_domain == "source_preserved_unknown"


# ── scope_ref propagation ───────────────────────────────────────────────


def test_unscoped_decision_events_yield_none_scope_ref() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref is None
    assert proj.decisions[0].scope_ref is None


def test_scoped_decision_summary_preserved() -> None:
    from ailuros.core.execution import DecisionSummary

    d = DecisionSummary(
        domain="security", decision="block", scope_ref="scope-abc"
    )
    assert d.scope_ref == "scope-abc"


def test_scoped_execution_projection_preserved() -> None:
    from ailuros.core.execution import ExecutionProjection, Lifecycle, Scope, Validation

    now = datetime.now(UTC)
    proj = ExecutionProjection(
        run_id="run-1",
        source="test",
        schema_version="1.0",
        lifecycle=Lifecycle.RUNNING,
        outcome=Outcome.UNKNOWN,
        validation=Validation.NOT_RUN,
        scope=Scope.UNKNOWN,
        started_at=now,
        scope_ref="scope-run-1",
    )
    assert proj.scope_ref == "scope-run-1"


def test_scoped_decision_event_propagates_scope_ref() -> None:
    events = [
        _event("run_started", event_id="e1", scope_ref="scope-run-1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
            scope_ref="scope-decision-2",
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref == "scope-run-1"
    assert proj.decisions[0].scope_ref == "scope-decision-2"


def test_unscoped_decision_event_does_not_inherit_run_scope() -> None:
    events = [
        _event("run_started", event_id="e1", scope_ref="scope-run-1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref == "scope-run-1"
    assert proj.decisions[0].scope_ref is None


def test_malformed_event_scope_ref_does_not_invent_identity() -> None:
    events = [
        _event("run_started", event_id="e1", scope_ref=42),  # type: ignore[arg-type]
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
            scope_ref=["scope-decision-2"],  # type: ignore[arg-type]
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref is None
    assert proj.decisions[0].scope_ref is None


# ── imported external_evidence wrapper scope propagation ────────────────


def _external_wrapper(
    inner_event_type: str,
    *,
    event_id: str,
    payload: dict | None = None,
    scope_ref: str | None = None,
    wrapper_scope_ref: str | None = None,
) -> dict:
    wrapper_payload: dict = {
        "event_type": inner_event_type,
        "payload": payload or {},
        "metadata": {},
    }
    if wrapper_scope_ref is not None:
        wrapper_payload["scope_ref"] = wrapper_scope_ref
    event = {
        "event_id": event_id,
        "event_type": "external_evidence",
        "timestamp": datetime.now(UTC),
        "payload": wrapper_payload,
    }
    if scope_ref is not None:
        event["scope_ref"] = scope_ref
    return event


def test_external_wrapper_scoped_event_projects_scope() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _external_wrapper(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
            wrapper_scope_ref="scope-wrapper-2",
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref == "scope-wrapper-2"
    assert proj.decisions[0].scope_ref == "scope-wrapper-2"


def test_external_wrapper_unscoped_projects_no_scope() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _external_wrapper(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref is None
    assert proj.decisions[0].scope_ref is None


def test_external_wrapper_malformed_scope_is_ignored() -> None:
    events = [
        _event("run_started", event_id="e1"),
        {
            "event_id": "e2",
            "event_type": "external_evidence",
            "timestamp": datetime.now(UTC),
            "payload": {
                "event_type": "governance_decision",
                "payload": {"decision": "block", "tool_name": "bash"},
                "metadata": {},
                "scope_ref": ["scope-bad"],  # type: ignore[dict-item]
            },
        },
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref is None
    assert proj.decisions[0].scope_ref is None


def test_external_wrapper_does_not_invent_scope_from_payload() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _external_wrapper(
            "run_started",
            event_id="e2",
            payload={"scope_ref": "payload-scope", "input": "x"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref is None


def test_native_scoped_event_still_projects_without_wrapper() -> None:
    events = [
        _event("run_started", event_id="e1", scope_ref="native-scope"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "bash"},
            scope_ref="native-scope",
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref == "native-scope"
    assert proj.decisions[0].scope_ref == "native-scope"
