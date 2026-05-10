from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from ailuros.models import GovernanceDecision


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    blocked: bool
    decision: GovernanceDecision
    result: Any = None
    error: str | None = None


WrappedTool = Callable[..., ToolExecutionResult]
