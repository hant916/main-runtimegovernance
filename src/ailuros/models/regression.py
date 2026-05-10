from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class RegressionComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_id: str
    baseline_run_id: str
    candidate_run_id: str
    passed: bool
    differences: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value
