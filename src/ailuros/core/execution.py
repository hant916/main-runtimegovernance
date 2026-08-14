from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ailuros._compat import StrEnum


class Lifecycle(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class Outcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"
    UNKNOWN = "unknown"


class Validation(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    NOT_RUN = "not_run"
    UNKNOWN = "unknown"


class Scope(StrEnum):
    CLEAN = "clean"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    artifact: str | None = None
    pointer: str | None = None


class RoleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class ChangeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str


class DecisionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    decision: str
    projected_domain: str = "source_preserved_unknown"


class GovernanceContextConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    values: list[str]
    source_pointers: list[str]


class GovernanceContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_ref: str | None = None
    workflow_ref: str | None = None
    invocation_ref: str | None = None
    policy_snapshot_ref: str | None = None
    source_pointers: list[str] = Field(default_factory=list)
    inconsistencies: list[GovernanceContextConflict] = Field(default_factory=list)


class ExecutionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    source: str
    schema_version: str
    lifecycle: Lifecycle
    outcome: Outcome
    validation: Validation
    scope: Scope
    started_at: datetime
    completed_at: datetime | None = None
    step_count: int = 0
    decision_count: int = 0
    event_count: int = 0
    roles: list[RoleSummary] = Field(default_factory=list)
    changes: list[ChangeSummary] = Field(default_factory=list)
    decisions: list[DecisionSummary] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    governance_context: GovernanceContext | None = None
    version: int = 1

    @field_validator("started_at", "completed_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value
