from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from ailuros.models.common import Severity


class EvaluationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    severity: Severity
    message: str
    metadata: dict[str, Any] = {}


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    run_id: str
    evaluator: str
    passed: bool
    findings: list[EvaluationFinding] = []
    metadata: dict[str, Any] = {}
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value
