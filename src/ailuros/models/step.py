from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from ailuros._compat import StrEnum

class StepType(StrEnum):
    USER_INPUT = "user_input"
    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    GOVERNANCE = "governance"
    EVALUATION = "evaluation"


class StepStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    run_id: str
    step_type: StepType
    status: StepStatus
    name: str | None = None
    metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value
