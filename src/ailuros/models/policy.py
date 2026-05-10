from typing import Any

from pydantic import BaseModel, ConfigDict

from ailuros._compat import StrEnum
from ailuros.models.common import Severity
from ailuros.models.decision import GovernanceDecisionType


class PolicyOperator(StrEnum):
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    CONTAINS = "contains"
    REGEX = "regex"


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    version: str
    decision: GovernanceDecisionType = GovernanceDecisionType.ALLOW
    severity: Severity
    enabled: bool = True
    description: str | None = None
    scope: dict[str, Any] = {}
    match: dict[str, Any]
    requires_previous_steps: dict[str, Any] = {}
    reason: str | None = None
