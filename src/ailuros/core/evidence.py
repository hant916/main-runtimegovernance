from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class EvidenceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    timestamp: datetime
    payload: dict[str, Any] = {}
    metadata: dict[str, Any] = {}

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class EvidencePackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    schema_version: str
    run_id: str
    events: list[EvidenceEvent] = []
    files: dict[str, str] = {}
    metadata: dict[str, Any] = {}
