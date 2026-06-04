from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    run_id: str
    event_type: str
    payload: dict[str, Any] = {}
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value
