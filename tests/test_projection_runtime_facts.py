from __future__ import annotations

from datetime import UTC, datetime

from ailuros.core.execution import Lifecycle, Outcome, Scope, Validation
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


# ── T1: Project validation ────────────────────────────────────────────


def test_no_validation_events_yields_unknown() -> None:
    proj = build_execution_projection("run-1", "test", [])
    assert proj.validation == Validation.UNKNOWN


def test_single_validation_passed_yields_passed() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={"status": "passed"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.validation == Validation.PASSED


def test_single_validation_failed_yields_failed() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={"status": "failed"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.validation == Validation.FAILED


def test_single_validation_not_run_yields_not_run() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={"status": "not_run"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.validation == Validation.NOT_RUN


def test_not_run_remains_distinct_from_passed() -> None:
    proj_not_run = build_execution_projection(
        "run-1", "test",
        [_event("project_validation", event_id="e1", payload={"status": "not_run"})],
    )
    proj_passed = build_execution_projection(
        "run-2", "test",
        [_event("project_validation", event_id="e1", payload={"status": "passed"})],
    )
    assert proj_not_run.validation == Validation.NOT_RUN
    assert proj_passed.validation == Validation.PASSED
    assert proj_not_run.validation != proj_passed.validation


def test_multiple_passed_yields_passed() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={"status": "passed"}),
        _event("project_validation", event_id="e2", payload={"status": "passed"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.validation == Validation.PASSED


def test_mixed_passed_and_not_run_yields_partial() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={"status": "passed"}),
        _event("project_validation", event_id="e2", payload={"status": "not_run"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.validation == Validation.PARTIAL


def test_failed_overrides_passed() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={"status": "passed"}),
        _event("project_validation", event_id="e2", payload={"status": "failed"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.validation == Validation.FAILED


def test_failed_overrides_not_run() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={"status": "not_run"}),
        _event("project_validation", event_id="e2", payload={"status": "failed"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.validation == Validation.FAILED


def test_validation_evidence_refs_captured() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={"status": "passed"}),
        _event("project_validation", event_id="e2", payload={"status": "failed"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    evt_ids = {r.event_id for r in proj.evidence_refs if r.event_id in ("e1", "e2")}
    assert evt_ids == {"e1", "e2"}


def test_unknown_status_string_ignored_in_validation() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={"status": ""}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.validation == Validation.UNKNOWN


# ── T2: Project changes / scope ───────────────────────────────────────


def test_no_scope_events_yields_unknown_scope() -> None:
    proj = build_execution_projection("run-1", "test", [])
    assert proj.scope == Scope.UNKNOWN


def test_clean_scope_yields_clean() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={"status": "clean"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope == Scope.CLEAN


def test_violated_scope_yields_violated() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={"status": "violated"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope == Scope.VIOLATED


def test_violated_overrides_clean() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={"status": "clean"}),
        _event("project_scope", event_id="e2", payload={"status": "violated"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope == Scope.VIOLATED


def test_changed_files_populate_changes() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={
            "status": "clean",
            "changed_files": ["src/a.py", "tests/b.py"],
        }),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert len(proj.changes) == 2
    descriptions = {c.description for c in proj.changes}
    assert descriptions == {"src/a.py", "tests/b.py"}


def test_scope_evidence_refs_captured() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={"status": "clean"}),
        _event("project_scope", event_id="e2", payload={"status": "violated"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    evt_ids = {r.event_id for r in proj.evidence_refs if r.event_id in ("e1", "e2")}
    assert evt_ids == {"e1", "e2"}


def test_missing_scope_evidence_yields_unknown() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("run_completed", event_id="e2"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope == Scope.UNKNOWN


def test_unknown_scope_status_keeps_unknown() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={"status": "other"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope == Scope.UNKNOWN


def test_empty_changed_files_does_not_add_changes() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={
            "status": "clean",
            "changed_files": [],
        }),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.changes == []


def test_changed_files_not_list_does_not_add_changes() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={
            "status": "clean",
            "changed_files": "not_a_list",
        }),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.changes == []


# ── T3: Project runtime roles ─────────────────────────────────────────


def test_no_role_events_yields_empty_roles() -> None:
    proj = build_execution_projection("run-1", "test", [])
    assert proj.roles == []


def test_single_runtime_role_captured() -> None:
    events = [
        _event("runtime_role", event_id="e1", payload={"name": "planner"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert len(proj.roles) == 1
    assert proj.roles[0].name == "planner"


def test_multiple_roles_deduplicated() -> None:
    events = [
        _event("runtime_role", event_id="e1", payload={"name": "planner"}),
        _event("runtime_role", event_id="e2", payload={"name": "executor"}),
        _event("runtime_role", event_id="e3", payload={"name": "planner"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    names = {r.name for r in proj.roles}
    assert names == {"planner", "executor"}
    assert len(proj.roles) == 2


def test_role_names_are_generic_strings() -> None:
    events = [
        _event("runtime_role", event_id="e1", payload={"name": "custom-agent"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.roles[0].name == "custom-agent"


def test_role_evidence_refs_captured() -> None:
    events = [
        _event("runtime_role", event_id="e1", payload={"name": "planner"}),
        _event("runtime_role", event_id="e2", payload={"name": "executor"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    evt_ids = {r.event_id for r in proj.evidence_refs if r.event_id in ("e1", "e2")}
    assert evt_ids == {"e1", "e2"}


def test_role_with_extra_facts_still_captures_name() -> None:
    events = [
        _event("runtime_role", event_id="e1", payload={
            "name": "planner",
            "provider": "openai",
            "model": "gpt-4",
        }),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert len(proj.roles) == 1
    assert proj.roles[0].name == "planner"


def test_empty_role_name_ignored() -> None:
    events = [
        _event("runtime_role", event_id="e1", payload={"name": ""}),
        _event("runtime_role", event_id="e2", payload={"name": "valid"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert len(proj.roles) == 1
    assert proj.roles[0].name == "valid"


# ── T4: Mixed / missing evidence ──────────────────────────────────────


def test_all_event_types_combined() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("runtime_role", event_id="e2", payload={"name": "planner"}),
        _event("project_validation", event_id="e3", payload={"status": "passed"}),
        _event("project_scope", event_id="e4", payload={
            "status": "clean",
            "changed_files": ["src/mod.py"],
        }),
        _event("governance_decision", event_id="e5", payload={
            "decision": "allow",
            "tool_name": "read",
        }),
        _event("run_completed", event_id="e6"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.lifecycle == Lifecycle.COMPLETED
    assert proj.outcome == Outcome.SUCCESS
    assert proj.validation == Validation.PASSED
    assert proj.scope == Scope.CLEAN
    assert len(proj.roles) == 1
    assert proj.roles[0].name == "planner"
    assert len(proj.changes) == 1
    assert proj.changes[0].description == "src/mod.py"
    assert len(proj.decisions) == 1
    assert proj.decision_count == 1
    assert proj.event_count == 6


def test_running_with_validation_and_scope() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("project_validation", event_id="e2", payload={"status": "failed"}),
        _event("project_scope", event_id="e3", payload={
            "status": "violated",
            "changed_files": ["src/forbidden.py"],
        }),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.lifecycle == Lifecycle.RUNNING
    assert proj.validation == Validation.FAILED
    assert proj.scope == Scope.VIOLATED
    assert len(proj.changes) == 1
    assert proj.changes[0].description == "src/forbidden.py"


def test_outcome_not_affected_by_validation_or_scope() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("project_validation", event_id="e2", payload={"status": "failed"}),
        _event("project_scope", event_id="e3", payload={
            "status": "violated",
            "changed_files": ["src/bad.py"],
        }),
        _event("runtime_role", event_id="e4", payload={"name": "executor"}),
        _event("run_completed", event_id="e5"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS
    assert proj.validation == Validation.FAILED
    assert proj.scope == Scope.VIOLATED


def test_partial_validation_from_mixed_events() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={"status": "passed"}),
        _event("project_validation", event_id="e2", payload={"status": "not_run"}),
        _event("project_validation", event_id="e3", payload={"status": "passed"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.validation == Validation.PARTIAL


def test_roles_sorted_for_determinism() -> None:
    events = [
        _event("runtime_role", event_id="e1", payload={"name": "zulu"}),
        _event("runtime_role", event_id="e2", payload={"name": "alpha"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert [r.name for r in proj.roles] == ["alpha", "zulu"]


def test_changes_preserve_order_of_encounter() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={
            "status": "clean",
            "changed_files": ["first.py", "second.py"],
        }),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert [c.description for c in proj.changes] == ["first.py", "second.py"]


def test_multiple_scope_changes_accumulate() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={
            "status": "clean",
            "changed_files": ["a.py"],
        }),
        _event("project_scope", event_id="e2", payload={
            "status": "clean",
            "changed_files": ["b.py"],
        }),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert [c.description for c in proj.changes] == ["a.py", "b.py"]


def test_failed_no_override_for_non_capability_reasons() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("project_validation", event_id="e2", payload={"status": "failed"}),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS
    assert proj.lifecycle == Lifecycle.COMPLETED


# ── EverRun post-fix validation/scope payload shapes ───────────────────


def test_everrun_validation_payload_projects_passed() -> None:
    events = [
        _event("project_validation", event_id="e1", payload={
            "failed_count": 0,
            "passed": True,
            "passed_commands": ["python -m pytest tests -q"],
            "passed_count": 1,
            "status": "passed",
        }),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.validation == Validation.PASSED


def test_everrun_scope_payload_projects_clean_and_changes() -> None:
    events = [
        _event("project_scope", event_id="e1", payload={
            "allowed_scope": True,
            "baseline_commit": "30cbad6baba05255b4f9ec9ce6783ed000026dc7",
            "changed_files": ["docs/operations/everrun-dogfood.md"],
            "changed_files_count": 1,
            "changed_files_source": "pack_start_baseline",
            "forbidden_touched": False,
            "status": "clean",
        }),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope == Scope.CLEAN
    assert [c.description for c in proj.changes] == ["docs/operations/everrun-dogfood.md"]


def test_everrun_sample_leaves_missing_governance_dimensions_unknown() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("project_validation", event_id="e2", payload={"status": "passed"}),
        _event("project_scope", event_id="e3", payload={
            "status": "clean",
            "changed_files": ["docs/operations/everrun-dogfood.md"],
        }),
        _event("governance_decision", event_id="e4", payload={
            "decision": "accept",
            "domain": "execution_control",
        }),
        _event("run_completed", event_id="e5"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.approval_records == []
    assert proj.budget_records == []
    assert proj.authority_records == []
    assert proj.lifecycle == Lifecycle.COMPLETED
    assert proj.outcome == Outcome.SUCCESS
