from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from ailuros._compat import StrEnum
from ailuros.models.common import Severity


class GovernanceDecisionType(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    SANITIZE = "sanitize"
    REQUIRE_REVIEW = "require_review"
    BLOCK = "block"


class GovernanceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    run_id: str
    decision: GovernanceDecisionType
    allowed: bool
    reason: str
    severity: Severity = Severity.LOW
    matched_policy_ids: list[str] = []
    metadata: dict[str, Any] = {}
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value
