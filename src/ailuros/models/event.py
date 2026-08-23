from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from ailuros._compat import StrEnum


class RuntimeEventType(StrEnum):
    RUN_STARTED = "run_started"
    USER_INPUT_RECEIVED = "user_input_received"
    INPUT_CLASSIFIED = "input_classified"
    AGENT_PLAN_CREATED = "agent_plan_created"
    AGENT_MESSAGE = "agent_message"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL_REQUESTED = "tool_call_requested"
    PATH_VALIDATION_RESULT = "path_validation_result"
    POLICY_EVALUATION_RESULT = "policy_evaluation_result"
    GOVERNANCE_DECISION = "governance_decision"
    TOOL_CALL_EXECUTED = "tool_call_executed"
    TOOL_CALL_BLOCKED = "tool_call_blocked"
    TOOL_RESULT_RECEIVED = "tool_result_received"
    OUTPUT_GENERATED = "output_generated"
    EVALUATION_RESULT = "evaluation_result"
    HUMAN_REVIEW_REQUESTED = "human_review_requested"
    HUMAN_REVIEW_COMPLETED = "human_review_completed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    REPLAY_STARTED = "replay_started"
    REPLAY_COMPLETED = "replay_completed"
    REGRESSION_COMPARISON_RESULT = "regression_comparison_result"
    PAYLOAD_REDACTED = "payload_redacted"
    EVIDENCE = "evidence"
    EXTERNAL_EVIDENCE = "external_evidence"


class RuntimeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    run_id: str
    step_id: str | None = None
    event_type: RuntimeEventType
    timestamp: datetime
    payload: dict[str, Any] = {}
    sequence: int | None = None
    scope_ref: str | None = None

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
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value
