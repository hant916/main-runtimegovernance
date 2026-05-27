from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from ailuros.adapters.models import AdapterContext, AdapterDecisionStatus, AdapterResult
from ailuros.models import GovernanceDecisionType


class _RuntimeProtocol(Protocol):
    def before_tool_call(
        self,
        run_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> Any: ...


@runtime_checkable
class ToolAdapter(Protocol):
    def execute_tool(
        self,
        fn: Callable[..., Any],
        context: AdapterContext,
    ) -> AdapterResult:
        ...


class LocalCallableAdapter:
    def __init__(self, runtime: _RuntimeProtocol) -> None:
        self._runtime = runtime

    def execute_tool(
        self,
        fn: Callable[..., Any],
        context: AdapterContext,
    ) -> AdapterResult:
        decision = self._runtime.before_tool_call(
            run_id=context.run_id,
            tool_name=context.tool_name,
            arguments=context.arguments,
            metadata=context.metadata,
        )
        if not decision.allowed:
            if decision.decision == GovernanceDecisionType.REQUIRE_REVIEW:
                return AdapterResult(
                    status=AdapterDecisionStatus.REQUIRES_REVIEW,
                    decision=decision,
                    reason=decision.reason,
                )
            return AdapterResult(
                status=AdapterDecisionStatus.BLOCKED,
                decision=decision,
                reason=decision.reason,
            )
        result = fn(**context.arguments)
        return AdapterResult(
            status=AdapterDecisionStatus.ALLOWED,
            decision=decision,
            reason=decision.reason,
            result=result,
        )
