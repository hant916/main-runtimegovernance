# Ailuros Governance Runtime — Python-first Impl Pack v2

Version: v2.0  
Status: Revised architecture  
Major change: **Python-first in-process SDK**, not TypeScript-first runtime.

---

## 0. Architecture Decision

Ailuros MVP is:

```text
Python Agent Runtime
        ↓
Ailuros Python SDK
        ↓
Ailuros Runtime Core
        ↓
SQLite
```

Not:

```text
TypeScript-first runtime core
HTTP server first
Sidecar first
Gateway first
```

Reason: the primary agent framework ecosystem is Python-first: LangGraph, OpenAI Agents SDK, CrewAI, AutoGen, PydanticAI, and LlamaIndex.

Core principle:

> Agent owns execution. Ailuros governs execution.

Ailuros does not replace agent frameworks. It integrates through lifecycle hooks.

---

## 1. MVP Stack

| Layer | Decision |
|---|---|
| Language | Python 3.11+ |
| Runtime Core | Python package |
| SDK | Python in-process SDK |
| CLI | Typer |
| Models | Pydantic v2 |
| Storage | SQLite |
| DB Access | Python `sqlite3` |
| Tests | pytest |
| Lint / Format | ruff |
| Type Check | mypy or pyright |
| Server | Not MVP |
| UI | Not MVP |

Do not introduce in MVP:

- FastAPI server
- HTTP gateway
- sidecar
- Redis
- Postgres
- Kafka
- Celery
- Temporal
- Kubernetes
- LangChain dependency in core
- LangGraph dependency in core
- web dashboard

---

## 2. Future Cross-Language Plan

Phase 2 may introduce:

```text
Python / TS / Java SDK
        ↓ HTTP JSON
Ailuros Runtime Server
        ↓
SQLite / Postgres later
```

Runtime Server can be FastAPI:

```bash
ailuros serve --port 4318
```

But this is not MVP.

---

## 3. Runtime Hook Contract

Ailuros core exposes:

```python
runtime.start_run(...)
runtime.record_agent_plan(...)
runtime.record_llm_request(...)
runtime.record_llm_response(...)
runtime.before_tool_call(...)
runtime.after_tool_call(...)
runtime.evaluate_output(...)
runtime.complete_run(...)
runtime.fail_run(...)
runtime.wrap_tool(...)
```

Critical hook:

```python
decision = runtime.before_tool_call(...)

if not decision.allowed:
    return blocked_result
```

Canonical events:

```text
run_started
user_input_received
input_classified
agent_plan_created
agent_message
llm_request
llm_response
tool_call_requested
path_validation_result
policy_evaluation_result
governance_decision
tool_call_executed
tool_call_blocked
tool_result_received
output_generated
evaluation_result
human_review_requested
human_review_completed
run_completed
run_failed
replay_started
replay_completed
regression_comparison_result
payload_redacted
```

---

## 4. Milestones

1. Python Repository Bootstrap
2. Runtime Trace Core
3. Policy Gateway
4. Path Validation
5. Evaluation Harness
6. Audit and Replay
7. Regression Comparator
8. First Framework Adapter Spike

---

## 5. Build Order

```text
01 bootstrap python package
02 runtime data models
03 sqlite storage
04 runtime lifecycle APIs
05 CLI run timeline
06 policy loader
07 policy matcher
08 before_tool_call decision flow
09 generic tool wrapper
10 refund demo
11 path validator
12 path integration
13 evaluation harness
14 customer email evaluator
15 audit reporter
16 recorded replay
17 regression comparator
18 LangGraph adapter spike
```

---

## 6. GitHub Labels

```text
type:setup
type:core
type:storage
type:runtime
type:cli
type:policy
type:path
type:evaluation
type:audit
type:replay
type:regression
type:example
type:adapter
type:docs
priority:high
priority:medium
priority:low
```

---

---

# Issue 001 — Bootstrap Python package with runtime, CLI, and refund example

## GitHub Issue

```text
Title: Bootstrap Python package with runtime, CLI, and refund example
Labels: type:setup, priority:high
Milestone: 0 - Python Repository Bootstrap
Dependencies: None
```

## Codex Impl Pack


### Goal

Create the Python package foundation.

### Files

```text
pyproject.toml
README.md
.gitignore
src/ailuros/__init__.py
src/ailuros/__main__.py
src/ailuros/runtime.py
src/ailuros/cli.py
tests/test_smoke.py
examples/refund_agent/main.py
```

### Stack

- Python 3.11+
- Pydantic v2
- Typer
- pytest
- ruff
- mypy or pyright

### Required Behavior

`src/ailuros/runtime.py`:

```python
class AilurosRuntime:
    name = "AilurosRuntime"

    def get_version(self) -> str:
        return "0.0.0"
```

`src/ailuros/__init__.py`:

```python
from .runtime import AilurosRuntime

__all__ = ["AilurosRuntime"]
```

CLI:

```bash
python -m ailuros --help
python -m ailuros version
```

Version prints:

```text
0.0.0
```

Refund example imports and instantiates `AilurosRuntime`.

### Constraints

- No HTTP server.
- No database.
- No policy engine.
- No replay.
- No path validator.
- No framework adapters.

### Verification

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ailuros --help
python -m ailuros version
python examples/refund_agent/main.py
```

### Output Format

```markdown
## Summary
## Files Changed
## Commands Run
## Test Results
## Notes / Follow-ups
```


---

# Issue 002 — Define Python runtime models

## GitHub Issue

```text
Title: Define Python runtime models
Labels: type:core, priority:high
Milestone: 1 - Runtime Trace Core
Dependencies: Issue 001
```

## Codex Impl Pack


### Goal

Define Pydantic v2 models for:

- Run
- Step
- RuntimeEvent
- GovernanceDecision
- Policy
- EvaluationResult
- ReplayResult
- AuditReport
- RegressionComparisonResult

### Files

```text
src/ailuros/models/common.py
src/ailuros/models/run.py
src/ailuros/models/step.py
src/ailuros/models/event.py
src/ailuros/models/decision.py
src/ailuros/models/policy.py
src/ailuros/models/evaluation.py
src/ailuros/models/replay.py
src/ailuros/models/audit.py
src/ailuros/models/regression.py
src/ailuros/models/__init__.py
tests/test_models.py
```

### Required Enums

Use `StrEnum`.

Common:

```python
class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"

class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

RunStatus:

```text
started
running
completed
failed
blocked
requires_review
replayed
```

GovernanceDecisionType:

```text
allow
block
require_review
warn
sanitize
```

RuntimeEventType must include all canonical events listed in this document.

### Required Models

Use timezone-aware `datetime`.

Use `metadata: dict[str, Any] = Field(default_factory=dict)`.

Example:

```python
class Run(BaseModel):
    run_id: str
    agent_id: str
    user_id: str | None = None
    environment: Environment
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### Tests

- create each model
- serialize to JSON
- validate enum values
- reject invalid enum values

### Verification

```bash
python -m pytest
python -m ruff check .
python -m mypy src
```

### Output Format

```markdown
## Summary
## Files Changed
## Model Design Notes
## Commands Run
## Test Results
## Follow-ups
```


---

# Issue 003 — Implement SQLite storage

## GitHub Issue

```text
Title: Implement SQLite storage
Labels: type:storage, priority:high
Milestone: 1 - Runtime Trace Core
Dependencies: Issue 002
```

## Codex Impl Pack


### Goal

Create local SQLite persistence.

### Files

```text
src/ailuros/storage/sqlite_storage.py
src/ailuros/storage/migrations/001_initial.sql
src/ailuros/storage/__init__.py
tests/test_sqlite_storage.py
```

### Tables

```text
runs
steps
events
governance_decisions
evaluations
audit_reports
replay_runs
migrations
```

### Key Rules

- Events are append-only.
- Do not expose event update/delete APIs.
- Store flexible payloads as JSON text.
- Tests use temporary DB files.
- Use standard library `sqlite3`.
- No ORM in MVP.

### Required API

```python
class SQLiteStorage:
    def __init__(self, path: str | Path): ...
    def init(self) -> None: ...

    def create_run(self, run: Run) -> None: ...
    def get_run(self, run_id: str) -> Run | None: ...
    def list_runs(self, limit: int = 20) -> list[Run]: ...
    def update_run_status(self, run_id: str, status: RunStatus, ended_at: datetime | None = None) -> None: ...

    def create_step(self, step: Step) -> None: ...
    def get_step(self, step_id: str) -> Step | None: ...
    def update_step_status(self, step_id: str, status: StepStatus, ended_at: datetime | None = None) -> None: ...

    def append_event(self, event: RuntimeEvent) -> None: ...
    def list_events(self, run_id: str) -> list[RuntimeEvent]: ...

    def save_governance_decision(self, decision: GovernanceDecision) -> None: ...
    def save_evaluation(self, result: EvaluationResult) -> None: ...
    def save_audit_report(self, report: AuditReport) -> None: ...
    def save_replay_result(self, result: ReplayResult) -> None: ...
```

### Event Sequence

`append_event()` assigns increasing `sequence` per run transactionally.

`list_events()` returns sequence ascending.

### Errors

Create:

```python
AilurosStorageError
AilurosNotFoundError
AilurosDataCorruptionError
```

### Tests

- DB init
- migration applied once
- run create/get/list/update
- step create/get/update
- event append/list/order
- JSON roundtrip
- decision/evaluation/audit/replay save
- no public event update method

### Verification

```bash
python -m pytest
python -m ruff check .
python -m mypy src
```


---

# Issue 004 — Implement runtime lifecycle APIs

## GitHub Issue

```text
Title: Implement runtime lifecycle APIs
Labels: type:runtime, priority:high
Milestone: 1 - Runtime Trace Core
Dependencies: Issue 003
```

## Codex Impl Pack


### Goal

Implement first usable SDK surface.

### Files

```text
src/ailuros/runtime/runtime.py
src/ailuros/runtime/ids.py
src/ailuros/runtime/clock.py
src/ailuros/runtime/__init__.py
tests/test_runtime_lifecycle.py
```

### Constructor

```python
runtime = AilurosRuntime(
    agent_id="support_refund_agent",
    environment="development",
    storage_path="./ailuros.sqlite",
)
```

### Required API

```python
def start_run(self, input: str, user_id: str | None = None, metadata: dict | None = None) -> Run: ...
def complete_run(self, run_id: str, output: str | None = None, status: RunStatus = RunStatus.COMPLETED, metadata: dict | None = None) -> None: ...
def fail_run(self, run_id: str, message: str, code: str | None = None, metadata: dict | None = None) -> None: ...
def record_event(self, run_id: str, event_type: RuntimeEventType, payload: dict | None = None, step_id: str | None = None) -> RuntimeEvent: ...
def record_tool_result(self, run_id: str, tool_name: str, result: dict, arguments: dict | None = None, step_id: str | None = None) -> RuntimeEvent: ...
def list_events(self, run_id: str) -> list[RuntimeEvent]: ...
```

### Required Behavior

`start_run()` appends:

```text
run_started
user_input_received
```

`complete_run()` appends:

```text
output_generated
run_completed
```

`fail_run()` appends:

```text
run_failed
```

`record_tool_result()` appends:

```text
tool_result_received
```

Payload uses snake_case:

```json
{
  "tool_name": "order.get_status",
  "arguments": {},
  "result": {}
}
```

### ID Rules

Use `uuid.uuid4().hex` with prefixes:

```text
run_
step_
evt_
dec_
eval_
audit_
```

### Tests

- start creates run and events
- complete updates status and appends event
- fail updates status and appends event
- record_event works
- record_tool_result works
- unknown run fails clearly
- event order is stable

### Verification

```bash
python -m pytest
python -m ruff check .
```


---

# Issue 005 — Implement CLI run timeline

## GitHub Issue

```text
Title: Implement CLI run timeline
Labels: type:cli, priority:medium
Milestone: 1 - Runtime Trace Core
Dependencies: Issue 004
```

## Codex Impl Pack


### Goal

Add terminal inspection.

### Commands

```bash
ailuros run list
ailuros run show <run_id>
```

### Files

```text
src/ailuros/cli_run.py
tests/test_cli_run.py
```

### DB Path Resolution

Order:

1. `--db`
2. `AILUROS_DB`
3. `./ailuros.sqlite`

### Output

`run list`:

```text
Run ID              Agent                 Status            Started At
run_abc123          refund_demo_agent     completed         2026-05-06T10:00:00Z
```

`run show`:

```text
Run: run_abc123
Agent: refund_demo_agent
Status: requires_review

Timeline:
[001] run_started
[002] user_input_received
[003] tool_call_requested payment.issue_refund
[004] governance_decision require_review high
[005] run_completed
```

### Tests

Use Typer CliRunner.

- empty DB
- one run
- known run show
- unknown run error
- env DB path
- CLI DB path

### Verification

```bash
python -m pytest
python -m ruff check .
python -m ailuros run list
```


---

# Issue 006 — Implement policy loader and validation

## GitHub Issue

```text
Title: Implement policy loader and validation
Labels: type:policy, priority:high
Milestone: 2 - Policy Gateway
Dependencies: Issue 004
```

## Codex Impl Pack


### Goal

Load and validate JSON policies.

### Files

```text
src/ailuros/policy/loader.py
src/ailuros/policy/validator.py
src/ailuros/policy/errors.py
src/ailuros/policy/__init__.py
src/ailuros/cli_policy.py
tests/policy/fixtures/valid_refund_policy.json
tests/policy/fixtures/invalid_missing_id.json
tests/policy/fixtures/invalid_unknown_operator.json
tests/test_policy_loader.py
tests/test_cli_policy.py
```

### Policy Example

```json
{
  "policy_id": "refund.high_value_requires_review",
  "version": "1.0.0",
  "enabled": true,
  "description": "Refunds above 500 EUR require human review.",
  "match": {
    "tool_name": "payment.issue_refund",
    "arguments.amount_eur": {
      "gt": 500
    }
  },
  "decision": "require_review",
  "severity": "high"
}
```

### Required Validation

Required:

```text
policy_id
version
match
severity
```

Allowed operators:

```text
eq
neq
gt
gte
lt
lte
in
not_in
exists
not_exists
contains
regex
```

### API

```python
class PolicyLoader:
    def load_file(self, path: str | Path) -> Policy: ...
    def load_files(self, paths: list[str | Path]) -> list[Policy]: ...
    def load_directory(self, path: str | Path) -> list[Policy]: ...

class PolicyValidator:
    def validate(self, policy: object) -> Policy: ...
    def validate_many(self, policies: list[object]) -> list[Policy]: ...
```

### CLI

```bash
ailuros policy validate <path>
```

### Tests

- valid policy loads
- missing id/version/match fails
- unknown severity fails
- unknown decision fails
- unknown operator fails
- directory loading
- disabled policy validates
- CLI success/failure

### Verification

```bash
python -m pytest
python -m ruff check .
python -m ailuros policy validate tests/policy/fixtures/valid_refund_policy.json
```


---

# Issue 007 — Implement policy matcher

## GitHub Issue

```text
Title: Implement policy matcher
Labels: type:policy, priority:high
Milestone: 2 - Policy Gateway
Dependencies: Issue 006
```

## Codex Impl Pack


### Goal

Match tool call context against policies.

### Files

```text
src/ailuros/policy/matcher.py
src/ailuros/policy/operators.py
src/ailuros/utils/json_path.py
tests/test_json_path.py
tests/test_policy_operators.py
tests/test_policy_matcher.py
```

### Context

```python
class ToolCallContext(BaseModel):
    environment: Environment
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### API

```python
class PolicyMatcher:
    def matches(self, policy: Policy, context: ToolCallContext) -> bool: ...
    def match_details(self, policy: Policy, context: ToolCallContext) -> PolicyMatchResult: ...
```

### Operators

Implement:

```text
eq
neq
gt
gte
lt
lte
in
not_in
exists
not_exists
contains
regex
```

### Rules

- Plain values are `eq`.
- All scope conditions must pass.
- All match conditions must pass.
- Missing fields fail except for `not_exists`.
- Invalid regex fails safely.

### Tests

Cover each operator, nested paths, env scope, missing fields, invalid regex, multiple conditions.

### Verification

```bash
python -m pytest
python -m ruff check .
```


---

# Issue 008 — Implement before_tool_call decision flow

## GitHub Issue

```text
Title: Implement before_tool_call decision flow
Labels: type:runtime, type:policy, priority:high
Milestone: 2 - Policy Gateway
Dependencies: Issue 007
```

## Codex Impl Pack


### Goal

Main runtime interception API.

### Files

```text
src/ailuros/policy/engine.py
src/ailuros/policy/decision_resolver.py
tests/test_decision_resolver.py
tests/test_before_tool_call.py
```

### Runtime Constructor

```python
runtime = AilurosRuntime(
    agent_id="refund_demo_agent",
    environment="development",
    storage_path="./ailuros.sqlite",
    policies=["./policies/refund.json"],
)
```

### API

```python
def before_tool_call(
    self,
    run_id: str,
    tool_name: str,
    arguments: dict | None = None,
    metadata: dict | None = None,
) -> GovernanceDecision: ...
```

### Event Flow

Append:

```text
tool_call_requested
policy_evaluation_result
governance_decision
tool_call_blocked  # if disallowed
```

### Decision Priority

```text
block
require_review
sanitize
warn
allow
```

Severity priority:

```text
critical
high
medium
low
```

Allowed:

```python
allowed = decision in {"allow", "warn", "sanitize"}
```

### Default

No match:

```text
allow, allowed=True, severity=low, reason="No matching policy."
```

### Tests

- no policy allow
- high refund require_review
- block policy blocks
- warn allows
- disabled ignored
- multiple policy priority
- events appended
- unknown run fails

### Verification

```bash
python -m pytest
python -m ruff check .
```


---

# Issue 009 — Implement generic tool wrapper

## GitHub Issue

```text
Title: Implement generic tool wrapper
Labels: type:runtime, type:policy, priority:high
Milestone: 2 - Policy Gateway
Dependencies: Issue 008
```

## Codex Impl Pack


### Goal

Make governance harder to forget.

### API

```python
safe_tool = runtime.wrap_tool(
    name="payment.issue_refund",
    fn=issue_refund,
)
```

Usage:

```python
result = safe_tool(
    run_id=run.run_id,
    order_id="ORD-9231",
    amount_eur=780,
)
```

### Files

```text
src/ailuros/runtime/tool_wrapper.py
tests/test_tool_wrapper.py
```

### Result Model

```python
class ToolExecutionResult(BaseModel):
    blocked: bool
    decision: GovernanceDecision
    result: Any | None = None
    error: str | None = None
```

### Behavior

1. Extract `run_id`.
2. Remaining kwargs become tool arguments.
3. Call `before_tool_call()`.
4. If disallowed: do not execute function.
5. If allowed: execute function.
6. Call `after_tool_call()`.
7. Return structured result.

### Also Add

```python
def after_tool_call(...): ...
```

Append:

```text
tool_call_executed
tool_result_received
```

### Tests

- allowed executes
- blocked does not execute
- after hook recorded
- missing run_id fails
- args passed correctly
- decision included

### Verification

```bash
python -m pytest
python -m ruff check .
```


---

# Issue 010 — Implement refund demo

## GitHub Issue

```text
Title: Implement refund demo
Labels: type:example, priority:high
Milestone: 2 - Policy Gateway
Dependencies: Issue 009
```

## Codex Impl Pack


### Goal

End-to-end proof that Ailuros blocks or pauses risky refund.

### Files

```text
examples/refund_agent/main.py
examples/refund_agent/policies/refund.json
examples/refund_agent/README.md
tests/test_refund_demo.py
```

### Scenario

1. User asks for refund.
2. Agent records order status.
3. Agent attempts refund of 780 EUR through wrapped tool.
4. Policy returns require_review.
5. Refund function is not executed.
6. Run completes as `requires_review`.

### Policy

```json
{
  "policy_id": "refund.high_value_requires_review",
  "version": "1.0.0",
  "enabled": true,
  "description": "Refunds above 500 EUR require human review.",
  "match": {
    "tool_name": "payment.issue_refund",
    "arguments.amount_eur": {
      "gt": 500
    }
  },
  "decision": "require_review",
  "severity": "high"
}
```

### Tests

- status requires_review
- tool_call_requested exists
- governance_decision exists
- original refund function not called
- no successful refund result

### Verification

```bash
python -m pytest
python -m ruff check .
python examples/refund_agent/main.py
python -m ailuros run list
```


---

# Issue 011 — Implement path validator

## GitHub Issue

```text
Title: Implement path validator
Labels: type:path, priority:high
Milestone: 3 - Path Validation
Dependencies: Issue 008
```

## Codex Impl Pack


### Goal

Validate required previous steps.

### Files

```text
src/ailuros/path/models.py
src/ailuros/path/loader.py
src/ailuros/path/validator.py
src/ailuros/path/__init__.py
tests/test_path_loader.py
tests/test_path_validator.py
examples/refund_agent/paths/refund_standard_flow.json
```

### Path Example

```json
{
  "path_id": "refund_standard_flow_v1",
  "version": "1.0.0",
  "steps": [
    {"name": "order.get_status", "required": true},
    {"name": "policy.lookup_refund_rule", "required": true},
    {
      "name": "payment.issue_refund",
      "required": false,
      "requires": ["order.get_status", "policy.lookup_refund_rule"]
    }
  ]
}
```

### API

```python
class PathValidator:
    def validate_before_tool_call(self, input: PathValidationInput) -> PathValidationResult: ...
```

### Previous Step Exists If

Event history contains:

```text
tool_result_received
```

or:

```text
tool_call_executed
```

with matching `payload.tool_name`.

### Tests

- path loads
- missing path_id fails
- required steps pass
- missing order check fails
- missing policy lookup fails
- unknown tool passes
- violation includes missing step
- recommended decision block

### Verification

```bash
python -m pytest
python -m ruff check .
```


---

# Issue 012 — Integrate path validation

## GitHub Issue

```text
Title: Integrate path validation
Labels: type:runtime, type:path, priority:high
Milestone: 3 - Path Validation
Dependencies: Issue 011
```

## Codex Impl Pack


### Goal

Path validation affects `before_tool_call()`.

### Runtime Constructor

```python
runtime = AilurosRuntime(
    agent_id="refund_demo_agent",
    environment="development",
    storage_path="./ailuros.sqlite",
    policies=["./policies/refund.json"],
    paths=["./paths/refund_standard_flow.json"],
)
```

### Event Flow

```text
tool_call_requested
path_validation_result
policy_evaluation_result
governance_decision
tool_call_blocked
```

### Decision Rules

- Any path block => final decision block.
- Path block beats policy allow/warn/require_review.
- matched_policy_ids remains policy-only.
- path violations go to metadata.

### Tests

- missing order status blocks
- missing policy lookup blocks
- path block wins
- path result event stored
- decision explains path violation

### Demo Update

Refund demo should skip policy lookup and become `blocked`.

### Verification

```bash
python -m pytest
python -m ruff check .
python examples/refund_agent/main.py
```


---

# Issue 013 — Implement evaluation harness

## GitHub Issue

```text
Title: Implement evaluation harness
Labels: type:evaluation, priority:high
Milestone: 4 - Evaluation Harness
Dependencies: Issue 004
```

## Codex Impl Pack


### Goal

Register and run evaluators.

### Files

```text
src/ailuros/evaluation/evaluator.py
src/ailuros/evaluation/harness.py
src/ailuros/evaluation/__init__.py
tests/test_evaluation_harness.py
```

### API

```python
class EvaluationHarness:
    def register(self, evaluator: Evaluator) -> None: ...
    def get(self, evaluator_id: str) -> Evaluator | None: ...
    def evaluate(self, evaluator_id: str, input: EvaluationInput) -> EvaluationResult: ...
    def evaluate_many(self, evaluator_ids: list[str], input: EvaluationInput) -> list[EvaluationResult]: ...
```

Runtime:

```python
def evaluate_output(
    self,
    run_id: str,
    output: str,
    evaluators: list[str],
    target_step_id: str | None = None,
    metadata: dict | None = None,
) -> list[EvaluationResult]: ...
```

### Behavior

- verify run exists
- call evaluators
- save results
- append `evaluation_result`
- unknown evaluator fails

### Tests

- register/get
- evaluate one/many
- unknown evaluator
- runtime stores result
- event appended

### Verification

```bash
python -m pytest
python -m ruff check .
```


---

# Issue 014 — Implement customer email evaluator

## GitHub Issue

```text
Title: Implement customer email evaluator
Labels: type:evaluation, priority:medium
Milestone: 4 - Evaluation Harness
Dependencies: Issue 013
```

## Codex Impl Pack


### Goal

Rule-based evaluator for risky customer support emails.

### Files

```text
src/ailuros/evaluation/evaluators/customer_email.py
src/ailuros/evaluation/evaluators/__init__.py
tests/test_customer_email_evaluator.py
```

### Evaluator ID

```text
customer_email_quality_v1
```

### Rules

Unsupported refund promise:

```text
we will refund
refund immediately
guaranteed refund
your refund has been approved
```

Internal leakage:

```text
internal note
do not show customer
agent reasoning
system prompt
developer note
```

Aggressive tone:

```text
you failed to
obviously
as I already said
you should have
```

Sensitive data request:

```text
full card number
credit card number
password
security code
CVV
CVC
```

### Scoring

Start 1.0.

Subtract:

```text
critical: 0.6
high: 0.4
medium: 0.25
low: 0.1
```

Pass if score >= 0.8 and no high/critical findings.

### Tests

- safe email passes
- refund promise fails
- internal leakage fails
- aggressive low finding
- sensitive data critical
- empty output
- case-insensitive

### Verification

```bash
python -m pytest
python -m ruff check .
```


---

# Issue 015 — Implement audit reporter

## GitHub Issue

```text
Title: Implement audit reporter
Labels: type:audit, priority:high
Milestone: 5 - Audit and Replay
Dependencies: Issue 008 + Issue 013
```

## Codex Impl Pack


### Goal

Generate JSON and Markdown audit reports.

### Files

```text
src/ailuros/audit/reporter.py
src/ailuros/audit/risk.py
src/ailuros/audit/markdown.py
src/ailuros/audit/__init__.py
src/ailuros/cli_audit.py
tests/test_audit_reporter.py
tests/test_audit_markdown.py
tests/test_cli_audit.py
```

### Runtime API

```python
def generate_audit_report(self, run_id: str) -> AuditReport: ...
def render_audit_report_markdown(self, report: AuditReport) -> str: ...
```

### CLI

```bash
ailuros run audit <run_id>
```

### Risk Rules

- warn/eval low-medium => medium
- require_review/eval high => high
- block/eval critical => critical

### Include Events

```text
tool_call_requested
governance_decision
tool_call_blocked
evaluation_result
path_validation_result
run_failed
```

### Tests

- simple report
- decisions included
- risk escalation
- markdown includes run ID/key events
- CLI works

### Verification

```bash
python -m pytest
python -m ruff check .
```


---

# Issue 016 — Implement recorded replay

## GitHub Issue

```text
Title: Implement recorded replay
Labels: type:replay, priority:high
Milestone: 5 - Audit and Replay
Dependencies: Issue 004
```

## Codex Impl Pack


### Goal

Replay using stored events only.

### Files

```text
src/ailuros/replay/engine.py
src/ailuros/replay/comparator.py
src/ailuros/replay/__init__.py
src/ailuros/cli_replay.py
tests/test_replay_engine.py
tests/test_replay_comparator.py
tests/test_cli_replay.py
```

### Runtime API

```python
def replay_recorded(self, source_run_id: str) -> ReplayResult: ...
```

### CLI

```bash
ailuros replay <run_id>
```

### Rules

- no live LLM calls
- no live tool calls
- create linked replay run
- append replay_started/replay_completed
- compare timeline
- ignore timestamps and generated IDs

### Tests

- replay completed run
- linked replay run
- no live tool call
- events appended
- missing source fails
- comparator detects difference

### Verification

```bash
python -m pytest
python -m ruff check .
```


---

# Issue 017 — Implement regression comparator

## GitHub Issue

```text
Title: Implement regression comparator
Labels: type:regression, priority:medium
Milestone: 6 - Regression Comparator
Dependencies: Issue 015 + Issue 016
```

## Codex Impl Pack


### Goal

Compare baseline and candidate runs.

### Files

```text
src/ailuros/regression/comparator.py
src/ailuros/regression/__init__.py
src/ailuros/cli_compare.py
tests/test_regression_comparator.py
tests/test_cli_compare.py
```

### Runtime API

```python
def compare_runs(self, baseline_run_id: str, candidate_run_id: str) -> RegressionComparisonResult: ...
```

### CLI

```bash
ailuros compare <baseline_run_id> <candidate_run_id>
```

### Compare

- tool-call sequence
- governance decisions
- new policy violations
- evaluation score delta
- final run status

### Fail If

- path changed
- new policy violations
- score_delta < -0.1
- candidate status worse than baseline

### Tests

- identical pass
- path changed fail
- new policy violation fail
- score drop fail
- candidate failed/blocked fail
- summary explains reason

### Verification

```bash
python -m pytest
python -m ruff check .
```


---

# Issue 018 — LangGraph adapter spike

## GitHub Issue

```text
Title: LangGraph adapter spike
Labels: type:adapter, priority:medium
Milestone: 7 - First Framework Adapter
Dependencies: Issue 010
```

## Codex Impl Pack


### Goal

Prove real framework integration through thin adapter.

### Target

LangGraph.

### Files

```text
src/ailuros/adapters/langgraph.py
src/ailuros/adapters/__init__.py
examples/langgraph_refund_agent/main.py
examples/langgraph_refund_agent/README.md
tests/test_langgraph_adapter.py
```

### Optional Dependency

```toml
[project.optional-dependencies]
langgraph = ["langgraph>=0.2"]
```

Do not make LangGraph a core dependency.

### Adapter Shape

```python
def wrap_langgraph_tool(
    runtime: AilurosRuntime,
    run_id: str,
    tool_name: str,
    fn: Callable[..., Any],
) -> Callable[..., Any]:
    ...
```

Adapter can delegate to `runtime.wrap_tool()`.

### Constraints

- no policy logic in adapter
- no replay logic in adapter
- no audit logic in adapter
- tests skip cleanly if LangGraph missing
- keep example minimal

### Tests

- adapter wraps function
- allowed tool executes
- blocked tool does not execute
- delegates to runtime
- no policy matching logic

### Verification

```bash
python -m pytest
python -m ruff check .
python -m pip install -e ".[dev,langgraph]"
python examples/langgraph_refund_agent/main.py
```


---

# GitHub Issue Creation JSON

```json
{
  "repository": "OWNER/ailuros",
  "milestones": [
    "0 - Python Repository Bootstrap",
    "1 - Runtime Trace Core",
    "2 - Policy Gateway",
    "3 - Path Validation",
    "4 - Evaluation Harness",
    "5 - Audit and Replay",
    "6 - Regression Comparator",
    "7 - First Framework Adapter"
  ],
  "issues": [
    {"id": "001", "title": "Bootstrap Python package with runtime, CLI, and refund example"},
    {"id": "002", "title": "Define Python runtime models"},
    {"id": "003", "title": "Implement SQLite storage"},
    {"id": "004", "title": "Implement runtime lifecycle APIs"},
    {"id": "005", "title": "Implement CLI run timeline"},
    {"id": "006", "title": "Implement policy loader and validation"},
    {"id": "007", "title": "Implement policy matcher"},
    {"id": "008", "title": "Implement before_tool_call decision flow"},
    {"id": "009", "title": "Implement generic tool wrapper"},
    {"id": "010", "title": "Implement refund demo"},
    {"id": "011", "title": "Implement path validator"},
    {"id": "012", "title": "Integrate path validation"},
    {"id": "013", "title": "Implement evaluation harness"},
    {"id": "014", "title": "Implement customer email evaluator"},
    {"id": "015", "title": "Implement audit reporter"},
    {"id": "016", "title": "Implement recorded replay"},
    {"id": "017", "title": "Implement regression comparator"},
    {"id": "018", "title": "LangGraph adapter spike"}
  ]
}
```

---

# Immediate Next Prompt

```markdown
We are building Ailuros, an open governance runtime for agentic AI systems.

Important architecture decision:

Ailuros MVP is Python-first.

It is an in-process Python SDK and runtime core.

Do not implement the TypeScript version.

Do not implement a local HTTP server yet.

Do not implement sidecar mode yet.

Your task is Issue 001 only:

# Bootstrap Python package with runtime, CLI, and refund example

Hard constraints:

- No HTTP server.
- No policy engine.
- No database.
- No replay.
- No path validator.
- No framework adapters.
- Only create package foundation.

Run:

python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ailuros --help
python -m ailuros version
python examples/refund_agent/main.py

Return:

## Summary
## Files Changed
## Commands Run
## Test Results
## Notes / Follow-ups
```

---

# Migration Note from v1

If the TypeScript bootstrap already exists, do not continue extending it as the runtime core.

Recommended option:

```text
legacy/typescript-bootstrap/
```

Then start the Python-first runtime cleanly.

Do not build a half-Python half-TypeScript MVP unless you want every future bug to have two passports.
