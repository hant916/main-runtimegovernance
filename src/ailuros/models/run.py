from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from ailuros._compat import StrEnum
from ailuros.models.common import Environment


class RunStatus(StrEnum):
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


class Run(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    agent_id: str
    environment: Environment
    status: RunStatus
    input: Any = None
    user_id: str | None = None
    metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value
