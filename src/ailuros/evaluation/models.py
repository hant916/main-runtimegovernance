from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ailuros.models import RuntimeEventType


class GovernanceDecisionExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["governance_decision"] = "governance_decision"
    decision: str | None = None
    allowed: bool | None = None
    severity: str | None = None


class BlockedToolExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["blocked_tool"] = "blocked_tool"
    tool_name: str
    decision: str | None = None


class AllowedToolExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["allowed_tool"] = "allowed_tool"
    tool_name: str


class ToolNotExecutedExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_not_executed"] = "tool_not_executed"
    tool_name: str


class PathValidationExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["path_validation"] = "path_validation"
    valid: bool
    path_id: str | None = None


class EventSequenceContainsExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["event_sequence_contains"] = "event_sequence_contains"
    event_types: list[RuntimeEventType]


class EvidenceEventExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["evidence_event"] = "evidence_event"
    evidence_event_type: str | None = None
    version: str | None = None
    payload_contains: dict[str, Any] | None = None


type EvaluationExpectation = Annotated[
    GovernanceDecisionExpectation
    | BlockedToolExpectation
    | AllowedToolExpectation
    | ToolNotExecutedExpectation
    | PathValidationExpectation
    | EventSequenceContainsExpectation
    | EvidenceEventExpectation,
    Field(discriminator="type"),
]


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    expectations: list[EvaluationExpectation]


class EvaluationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expectation_type: str
    event_type: RuntimeEventType | None = None
    sequence: int | None = None
    message: str


class EvaluationFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expectation_type: str
    message: str


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    passed: bool
    failures: list[EvaluationFailure]
    evidence: list[EvaluationEvidence]
