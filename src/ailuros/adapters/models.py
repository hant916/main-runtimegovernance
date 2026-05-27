from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from ailuros._compat import StrEnum
from ailuros.models import GovernanceDecision


class AdapterDecisionStatus(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REQUIRES_REVIEW = "requires_review"


class AdapterContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    tool_name: str
    arguments: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class AdapterResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: AdapterDecisionStatus
    decision: GovernanceDecision
    reason: str
    result: Any = None
