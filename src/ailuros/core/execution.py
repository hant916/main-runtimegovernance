from __future__ import annotations

from datetime import datetime
from typing import Any

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


class GovernedOutcome(StrEnum):
    CLEAN_SUCCESS = "clean_success"
    DEGRADED_SUCCESS = "degraded_success"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ScopeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_ref: str | None = None
    outcome: GovernedOutcome

    @field_validator("scope_ref", mode="before")
    @classmethod
    def require_scope_ref_string(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise ValueError("scope_ref must be a string or None")


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


class CoverageState(StrEnum):
    EVALUATED = "evaluated"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class GovernanceCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authority: CoverageState = CoverageState.UNKNOWN
    approval: CoverageState = CoverageState.UNKNOWN
    budget: CoverageState = CoverageState.UNKNOWN
    validation: CoverageState = CoverageState.UNKNOWN
    scope: CoverageState = CoverageState.UNKNOWN


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
    scope_ref: str | None = None

    @field_validator("scope_ref", mode="before")
    @classmethod
    def require_scope_ref_string(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise ValueError("scope_ref must be a string or None")


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


class ApprovalState(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    UNKNOWN = "unknown"


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    action: str | None = None
    required: bool | None = None
    decision: str | None = None
    state: ApprovalState
    approver_ref: str | None = None
    scope_ref: str | None = None
    timestamp: datetime | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)

    @field_validator("scope_ref", mode="before")
    @classmethod
    def require_scope_ref_string(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise ValueError("scope_ref must be a string or None")

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class BudgetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    unit: str
    scope_ref: str | None = None
    limit: float | None = None
    consumed: float | None = None
    remaining: float | None = None
    status: str = "unknown"
    required: bool | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)


class AuthorityState(StrEnum):
    AUTHORIZED = "authorized"
    VIOLATION = "violation"
    UNKNOWN = "unknown"


class AuthorityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str
    action: str | None = None
    observed_target: str | None = None
    requested_target: str | None = None
    authority_source: str | None = None
    scope_ref: str | None = None
    state: AuthorityState
    required: bool | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)

    @field_validator("scope_ref", mode="before")
    @classmethod
    def require_scope_ref_string(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise ValueError("scope_ref must be a string or None")


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
    scope_ref: str | None = None
    step_count: int = 0
    decision_count: int = 0
    event_count: int = 0
    roles: list[RoleSummary] = Field(default_factory=list)
    changes: list[ChangeSummary] = Field(default_factory=list)
    decisions: list[DecisionSummary] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    governance_context: GovernanceContext | None = None
    approval_records: list[ApprovalRecord] = Field(default_factory=list)
    budget_records: list[BudgetRecord] = Field(default_factory=list)
    authority_records: list[AuthorityRecord] = Field(default_factory=list)
    governance_coverage: GovernanceCoverage = Field(default_factory=GovernanceCoverage)
    version: int = 1

    @field_validator("scope_ref", mode="before")
    @classmethod
    def require_scope_ref_string(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise ValueError("scope_ref must be a string or None")

    @field_validator("started_at", "completed_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value
