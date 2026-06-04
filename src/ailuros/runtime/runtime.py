from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ailuros.errors import AilurosNotFoundError
from ailuros.models import (
    Environment,
    GovernanceDecision,
    GovernanceDecisionType,
    Run,
    RunStatus,
    RuntimeEvent,
    RuntimeEventType,
    Severity,
)
from ailuros.path import ExpectedPath, PathValidationResult, PathValidator
from ailuros.policy import DecisionResolver, PolicyEngine, PolicyLoader, ToolCallContext
from ailuros.runtime.clock import now_utc
from ailuros.runtime.ids import new_decision_id, new_event_id, new_run_id
from ailuros.runtime.tool_wrapper import ToolExecutionResult, WrappedTool
from ailuros.storage import SQLiteStorage


class AilurosRuntime:
    name = "AilurosRuntime"

    def __init__(
        self,
        agent_id: str = "default_agent",
        environment: Environment | str = Environment.DEVELOPMENT,
        storage_path: str | Path = "ailuros.sqlite",
        metadata: dict[str, Any] | None = None,
        policies: list[str | Path] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.environment = Environment(environment)
        self.metadata = metadata or {}
        self.storage = SQLiteStorage(storage_path)
        self.storage.init()
        loader = PolicyLoader()
        self.policies = loader.load_files(policies or [])
        self.policy_engine = PolicyEngine(self.policies)
        self.decision_resolver = DecisionResolver()

    def get_version(self) -> str:
        from ailuros import __version__

        return __version__

    def start_run(
        self, input: Any, user_id: str | None = None, metadata: dict[str, Any] | None = None
    ) -> Run:
        timestamp = now_utc()
        run = Run(
            run_id=new_run_id(),
            agent_id=self.agent_id,
            environment=self.environment,
            status=RunStatus.RUNNING,
            input=input,
            user_id=user_id,
            metadata={**self.metadata, **(metadata or {})},
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.storage.create_run(run)
        self.record_event(run.run_id, RuntimeEventType.RUN_STARTED, {"agent_id": self.agent_id})
        self.record_event(run.run_id, RuntimeEventType.USER_INPUT_RECEIVED, {"input": input})
        return run

    def complete_run(
        self,
        run_id: str,
        output: Any = None,
        status: RunStatus = RunStatus.COMPLETED,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._require_run(run_id)
        if output is not None:
            self.record_event(run_id, RuntimeEventType.OUTPUT_GENERATED, {"output": output})
        self.storage.update_run_status(run_id, status)
        self.record_event(
            run_id,
            RuntimeEventType.RUN_COMPLETED,
            {"status": status.value, "metadata": metadata or {}},
        )

    def fail_run(
        self,
        run_id: str,
        message: str,
        code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._require_run(run_id)
        self.storage.update_run_status(run_id, RunStatus.FAILED)
        self.record_event(
            run_id,
            RuntimeEventType.RUN_FAILED,
            {"message": message, "code": code, "metadata": metadata or {}},
        )

    def record_event(
        self,
        run_id: str,
        event_type: RuntimeEventType | str,
        payload: dict[str, Any] | None = None,
        step_id: str | None = None,
    ) -> RuntimeEvent:
        self._require_run(run_id)
        event = RuntimeEvent(
            event_id=new_event_id(),
            run_id=run_id,
            step_id=step_id,
            event_type=RuntimeEventType(event_type),
            timestamp=now_utc(),
            payload=payload or {},
        )
        return self.storage.append_event(event)

    def record_tool_result(
        self,
        run_id: str,
        tool_name: str,
        result: Any,
        arguments: dict[str, Any] | None = None,
        step_id: str | None = None,
    ) -> RuntimeEvent:
        return self.record_event(
            run_id,
            RuntimeEventType.TOOL_RESULT_RECEIVED,
            {"tool_name": tool_name, "arguments": arguments or {}, "result": result},
            step_id,
        )

    def list_events(self, run_id: str) -> list[RuntimeEvent]:
        return self.storage.list_events(run_id)

    def validate_path(
        self, run_id: str, expected_path: ExpectedPath
    ) -> PathValidationResult:
        self._require_run(run_id)
        result = PathValidator.validate(expected_path, self.list_events(run_id))
        self.record_event(
            run_id,
            RuntimeEventType.PATH_VALIDATION_RESULT,
            result.model_dump(mode="json"),
        )
        return result

    def before_tool_call(
        self,
        run_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GovernanceDecision:
        self._require_run(run_id)
        args = arguments or {}
        self.record_event(
            run_id,
            RuntimeEventType.TOOL_CALL_REQUESTED,
            {"tool_name": tool_name, "arguments": args, "metadata": metadata or {}},
        )
        prior_events_raw = self.storage.list_events(run_id)
        context = ToolCallContext(
            environment=self.environment,
            tool_name=tool_name,
            arguments=args,
            metadata=metadata or {},
            prior_events=[event.model_dump(mode="json") for event in prior_events_raw],
        )
        evaluation = self.policy_engine.evaluate_tool_call(context)
        self.record_event(
            run_id,
            RuntimeEventType.POLICY_EVALUATION_RESULT,
            {
                "matched_policy_ids": [policy.policy_id for policy in evaluation.matched_policies],
                "evaluated_policy_count": evaluation.evaluated_policy_count,
                "matched_policy_count": evaluation.matched_policy_count,
            },
        )
        decision = self.decision_resolver.resolve(run_id, evaluation.matched_policies).model_copy(
            update={
                "tool_name": tool_name,
                "input_hash": hashlib.sha256(
                    json.dumps(args, sort_keys=True).encode()
                ).hexdigest(),
            }
        )
        self.storage.save_governance_decision(decision)
        self.record_event(
            run_id,
            RuntimeEventType.GOVERNANCE_DECISION,
            decision.model_dump(mode="json"),
        )
        if not decision.allowed:
            self.record_event(
                run_id,
                RuntimeEventType.TOOL_CALL_BLOCKED,
                {
                    "tool_name": tool_name,
                    "decision": decision.decision.value,
                    "reason": decision.reason,
                },
            )
        return decision

    def after_tool_call(
        self,
        run_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        result: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.record_event(
            run_id,
            RuntimeEventType.TOOL_CALL_EXECUTED,
            {"tool_name": tool_name, "arguments": arguments or {}, "metadata": metadata or {}},
        )
        self.record_tool_result(run_id, tool_name, result, arguments)

    def wrap_tool(self, name: str, fn: Callable[..., Any]) -> WrappedTool:
        def wrapped(*args: Any, **kwargs: Any) -> ToolExecutionResult:
            if "run_id" not in kwargs:
                raise ValueError("wrapped tool requires run_id keyword argument")
            run_id = str(kwargs.pop("run_id"))
            tool_arguments = dict(kwargs)
            decision = self.before_tool_call(run_id, name, tool_arguments)
            if not decision.allowed:
                return ToolExecutionResult(blocked=True, decision=decision)
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                return ToolExecutionResult(
                    blocked=False, decision=decision, error=f"{type(exc).__name__}: {exc}"
                )
            self.after_tool_call(run_id, name, tool_arguments, result)
            return ToolExecutionResult(blocked=False, decision=decision, result=result)

        return wrapped

    def _require_run(self, run_id: str) -> Run:
        try:
            return self.storage.get_run(run_id)
        except AilurosNotFoundError:
            raise


def allow_decision(run_id: str) -> GovernanceDecision:
    return GovernanceDecision(
        decision_id=new_decision_id(),
        run_id=run_id,
        decision=GovernanceDecisionType.ALLOW,
        allowed=True,
        reason="No matching policy.",
        severity=Severity.LOW,
        created_at=now_utc(),
    )
