from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ailuros.core.execution import (
    ChangeSummary,
    DecisionSummary,
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    RoleSummary,
    Scope,
    Validation,
)


def test_lifecycle_enum_values() -> None:
    assert Lifecycle.RUNNING.value == "running"
    assert Lifecycle.COMPLETED.value == "completed"
    assert Lifecycle.FAILED.value == "failed"
    assert Lifecycle.UNKNOWN.value == "unknown"
    assert len(Lifecycle) == 4


def test_outcome_enum_values() -> None:
    assert Outcome.SUCCESS.value == "success"
    assert Outcome.PARTIAL.value == "partial"
    assert Outcome.BLOCKED.value == "blocked"
    assert Outcome.REVIEW_REQUIRED.value == "review_required"
    assert Outcome.FAILED.value == "failed"
    assert Outcome.UNKNOWN.value == "unknown"
    assert len(Outcome) == 6


def test_validation_enum_values() -> None:
    assert Validation.PASSED.value == "passed"
    assert Validation.FAILED.value == "failed"
    assert Validation.PARTIAL.value == "partial"
    assert Validation.NOT_RUN.value == "not_run"
    assert Validation.UNKNOWN.value == "unknown"
    assert len(Validation) == 5


def test_scope_enum_values() -> None:
    assert Scope.CLEAN.value == "clean"
    assert Scope.VIOLATED.value == "violated"
    assert Scope.UNKNOWN.value == "unknown"
    assert len(Scope) == 3


def test_evidence_ref_creation() -> None:
    ref = EvidenceRef(event_id="evt-1")
    assert ref.event_id == "evt-1"
    assert ref.artifact is None
    assert ref.pointer is None

    ref_full = EvidenceRef(event_id="evt-2", artifact="report.json", pointer="/runs/uuid/logs")
    assert ref_full.event_id == "evt-2"
    assert ref_full.artifact == "report.json"
    assert ref_full.pointer == "/runs/uuid/logs"


def test_evidence_ref_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        EvidenceRef(event_id="evt-1", extra_field="bad")


def test_evidence_ref_serializes_to_json() -> None:
    ref = EvidenceRef(event_id="evt-1", artifact="report.json")
    data = ref.model_dump(mode="json")
    assert data == {"event_id": "evt-1", "artifact": "report.json", "pointer": None}


def test_role_summary_creation() -> None:
    role = RoleSummary(name="planner")
    assert role.name == "planner"


def test_role_summary_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        RoleSummary(name="planner", extra="bad")


def test_change_summary_creation() -> None:
    change = ChangeSummary(description="renamed field X to Y")
    assert change.description == "renamed field X to Y"


def test_change_summary_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        ChangeSummary(description="test", extra="bad")


def test_decision_summary_creation() -> None:
    dec = DecisionSummary(domain="security", decision="block")
    assert dec.domain == "security"
    assert dec.decision == "block"


def test_decision_summary_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        DecisionSummary(domain="security", decision="block", extra="bad")


def test_execution_projection_minimal_construction() -> None:
    now = datetime.now(UTC)
    proj = ExecutionProjection(
        run_id="run-1",
        source="test-runner",
        schema_version="1.0",
        lifecycle=Lifecycle.RUNNING,
        outcome=Outcome.UNKNOWN,
        validation=Validation.NOT_RUN,
        scope=Scope.UNKNOWN,
        started_at=now,
    )
    assert proj.run_id == "run-1"
    assert proj.source == "test-runner"
    assert proj.schema_version == "1.0"
    assert proj.lifecycle == Lifecycle.RUNNING
    assert proj.outcome == Outcome.UNKNOWN
    assert proj.validation == Validation.NOT_RUN
    assert proj.scope == Scope.UNKNOWN
    assert proj.started_at == now
    assert proj.completed_at is None
    assert proj.step_count == 0
    assert proj.decision_count == 0
    assert proj.event_count == 0
    assert proj.roles == []
    assert proj.changes == []
    assert proj.decisions == []
    assert proj.evidence_refs == []
    assert proj.version == 1


def test_execution_projection_full_construction() -> None:
    now = datetime.now(UTC)
    later = now + timedelta(hours=1)
    proj = ExecutionProjection(
        run_id="run-2",
        source="test-runner",
        schema_version="1.0",
        lifecycle=Lifecycle.COMPLETED,
        outcome=Outcome.SUCCESS,
        validation=Validation.PASSED,
        scope=Scope.CLEAN,
        started_at=now,
        completed_at=later,
        step_count=5,
        decision_count=3,
        event_count=12,
        roles=[RoleSummary(name="planner"), RoleSummary(name="executor")],
        changes=[ChangeSummary(description="added field")],
        decisions=[DecisionSummary(domain="security", decision="allow")],
        evidence_refs=[EvidenceRef(event_id="evt-1", artifact="log.json")],
        version=2,
    )
    assert proj.lifecycle == Lifecycle.COMPLETED
    assert proj.outcome == Outcome.SUCCESS
    assert proj.validation == Validation.PASSED
    assert proj.scope == Scope.CLEAN
    assert proj.completed_at == later
    assert proj.step_count == 5
    assert len(proj.roles) == 2
    assert len(proj.changes) == 1
    assert len(proj.decisions) == 1
    assert len(proj.evidence_refs) == 1
    assert proj.version == 2


def test_execution_projection_extra_forbidden() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        ExecutionProjection(
            run_id="run-1",
            source="test",
            schema_version="1.0",
            lifecycle=Lifecycle.RUNNING,
            outcome=Outcome.UNKNOWN,
            validation=Validation.NOT_RUN,
            scope=Scope.UNKNOWN,
            started_at=now,
            extra_field="bad",
        )


def test_execution_projection_rejects_naive_started_at() -> None:
    with pytest.raises(ValidationError):
        ExecutionProjection(
            run_id="run-1",
            source="test",
            schema_version="1.0",
            lifecycle=Lifecycle.RUNNING,
            outcome=Outcome.UNKNOWN,
            validation=Validation.NOT_RUN,
            scope=Scope.UNKNOWN,
            started_at=datetime.now(),
        )


def test_execution_projection_rejects_naive_completed_at() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        ExecutionProjection(
            run_id="run-1",
            source="test",
            schema_version="1.0",
            lifecycle=Lifecycle.RUNNING,
            outcome=Outcome.UNKNOWN,
            validation=Validation.NOT_RUN,
            scope=Scope.UNKNOWN,
            started_at=now,
            completed_at=datetime.now(),
        )


def test_execution_projection_serializes_to_json() -> None:
    now = datetime.now(UTC)
    proj = ExecutionProjection(
        run_id="run-1",
        source="test-runner",
        schema_version="1.0",
        lifecycle=Lifecycle.COMPLETED,
        outcome=Outcome.SUCCESS,
        validation=Validation.PASSED,
        scope=Scope.CLEAN,
        started_at=now,
        completed_at=now + timedelta(hours=1),
        decisions=[DecisionSummary(domain="security", decision="allow")],
        evidence_refs=[EvidenceRef(event_id="evt-1")],
    )
    dump = proj.model_dump(mode="json")
    assert dump["run_id"] == "run-1"
    assert dump["source"] == "test-runner"
    assert dump["lifecycle"] == "completed"
    assert dump["outcome"] == "success"
    assert dump["validation"] == "passed"
    assert dump["scope"] == "clean"
    assert dump["version"] == 1
    assert isinstance(dump["started_at"], str)
    assert isinstance(dump["completed_at"], str)
    assert dump["step_count"] == 0
    assert dump["decision_count"] == 0
    assert dump["event_count"] == 0
    assert dump["roles"] == []
    assert dump["changes"] == []
    assert len(dump["decisions"]) == 1
    assert len(dump["evidence_refs"]) == 1


def test_enum_from_string() -> None:
    assert Lifecycle("running") == Lifecycle.RUNNING
    assert Outcome("blocked") == Outcome.BLOCKED
    assert Validation("not_run") == Validation.NOT_RUN
    assert Scope("clean") == Scope.CLEAN


def test_enum_rejects_invalid_value() -> None:
    with pytest.raises(ValueError):
        Lifecycle("nonexistent")
    with pytest.raises(ValueError):
        Outcome("nonexistent")
    with pytest.raises(ValueError):
        Validation("nonexistent")
    with pytest.raises(ValueError):
        Scope("nonexistent")
