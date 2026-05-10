from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class ReplayResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replay_id: str
    run_id: str
    status: str
    key_events: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value
