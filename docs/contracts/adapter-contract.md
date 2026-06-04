# Adapter Contract

This document defines the framework-neutral adapter contract for Ailuros.  
Future concrete adapters (MCP, LangChain, CrewAI, etc.) must satisfy this contract.

## Compliance

All adapters must pass the conformance harness at `tests/test_adapter_conformance.py`.

## Interface

Every adapter must implement the `ToolAdapter` protocol:

```python
from collections.abc import Callable
from typing import Any

from ailuros.adapters import AdapterContext, AdapterResult

class ToolAdapter(Protocol):
    def execute_tool(self, fn: Callable[..., Any], context: AdapterContext) -> AdapterResult:
        ...
```

The signature is the contract: no other public interface is required.

## AdapterContext

| Field       | Type                  | Required | Default | Description                    |
|-------------|-----------------------|----------|---------|--------------------------------|
| `run_id`    | `str`                 | yes      | —       | Unique run identifier          |
| `tool_name` | `str`                 | yes      | —       | Tool name for governance matching |
| `arguments` | `dict[str, Any]`      | no       | `{}`    | Keyword arguments passed to `fn` |
| `metadata`  | `dict[str, Any]`      | no       | `{}`    | Audit metadata (session, user, etc.) |

Extra fields are forbidden. The model uses `extra="forbid"`.

## AdapterResult

| Field      | Type                   | Description                              |
|------------|------------------------|------------------------------------------|
| `status`   | `AdapterDecisionStatus`| One of `allowed`, `blocked`, `requires_review` |
| `decision` | `GovernanceDecision`   | The governance decision that produced this result |
| `reason`   | `str`                  | Human-readable reason for the decision   |
| `result`   | `Any`                  | Tool output when allowed; `None` otherwise |

## Contract Rules

Future adapter implementations must satisfy every rule below.

### R1 — Call shape

`execute_tool(fn, context) -> AdapterResult` is the only entry point.  
No extra parameters, no side-channel configuration.

**Harness evidence**: `test_call_shape_conformance`, `test_local_callable_adapter_call_shape`

### R2 — Result shape

Every returned `AdapterResult` must have non-None `status`, `decision`, and `reason`.  
The `result` field is `None` unless the tool was allowed and executed successfully.

**Harness evidence**: `_assert_result_shape`, `test_result_status_values`, `test_result_null_result_on_blocked`

### R3 — Error mapping

Runtime governance failures (before_tool_call exceptions) must prevent tool execution.  
Tool execution errors must propagate to the caller; they must not be silently swallowed.  
When the tool raises, `record_tool_result` must not be called.

**Harness evidence**: `test_runtime_failure_prevents_tool_execution`, `test_tool_error_propagates_from_adapter`, `test_error_does_not_record_result`

### R4 — Audit metadata preservation

All `AdapterContext` fields (including `metadata`) must reach the governance runtime.  
Arguments must be passed unmodified to the tool function.

**Harness evidence**: `test_metadata_round_trip`, `test_execute_tool_passes_all_arguments`

### R5 — Strict schema

`AdapterContext` must reject unknown fields. Default values (`arguments={}`, `metadata={}`) must be honored.

**Harness evidence**: `test_context_extra_fields_forbidden`, `test_context_defaults_preserved`

## How to Implement a Future Adapter

1. Subclass or structurally satisfy `ToolAdapter` (passes `isinstance(adapter, ToolAdapter)`).
2. Accept `fn: Callable[..., Any]` and `context: AdapterContext` in `execute_tool`.
3. Call runtime governance (`.before_tool_call`) with all context fields.
4. If blocked/review: return `AdapterResult` with appropriate status, `result=None`.
5. If allowed: execute `fn(**context.arguments)`, record the result via `.record_tool_result`, return `AdapterResult(status=ALLOWED, result=...)`.
6. On governance failure: raise — the harness expects errors to propagate.
7. On tool failure: raise — the harness expects errors to propagate, no silent capture.
8. Run `python -m pytest tests/test_adapter_conformance.py -q` and ensure all tests pass.

## Anti-patterns

- Do not silently capture tool errors into `AdapterResult.result`.
- Do not add framework-specific dependencies to the adapter base layer.
- Do not weaken `AdapterContext` schema to accept extra fields.
- Do not call `record_tool_result` when the tool did not execute.
- Do not introduce side-effect-only adapters that skip `before_tool_call`.
