# ailuros

[Read the changelog](CHANGELOG.md) for the full v0.1.0 release summary.

ailuros is a Python governance runtime kernel for local agent runs. In v0.1 it provides an in-process runtime, policy-gated tool calls, SQLite-backed run timelines, explicit path validation, and read-only audit/replay CLI commands.

The primary example is the refund demo in `examples/refund_agent`, where a high-value refund request is blocked by policy before `payment.issue_refund` is invoked.

## v0.1 capabilities

- Start and complete local runtime runs.
- Record runtime events to a SQLite timeline.
- Wrap Python tool functions with a policy gate.
- Block a wrapped tool call when a matching policy returns a blocking decision.
- Validate an expected tool-call path against already-recorded timeline events.
- Inspect stored runs and timelines from the CLI.
- Replay a stored timeline by printing its events; replay does not invoke tools.
- Build a compact audit summary from stored events; audit does not recompute policy.
- Evaluate stored timelines against JSON golden cases; eval does not recompute policy or invoke tools.
- Validate JSON policy files from the CLI.

## Governance flow

```text
agent code
  -> start_run records a run
  -> record_tool_result can add observed tool output
  -> wrap_tool requests a tool call through the policy gate
  -> policy gate records the governance decision
  -> allowed calls execute the wrapped Python function
  -> blocked calls record the block and do not call the wrapped function
  -> validate_path compares an ExpectedPath with recorded tool-call events
  -> complete_run records the final run status and output
  -> run show, replay, audit, and eval read the stored timeline
```

Path validation is a recorded check over observed events. It reports missing required calls, forbidden observed calls, unexpected calls, and malformed tool-call events. It is not documented here as an execution blocker; in the refund demo, the refund is blocked by policy before the refund function can run.

Audit, replay, and eval are read-only CLI views over stored timeline data. `replay` prints the stored event sequence. `audit` summarizes the stored decision, reason, tool, and path-validation status. `eval` loads JSON `EvaluationCase` files and prints PASS/FAIL with evidence sequence references.

## Quickstart

From the repository root, install the package in editable mode with development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Check the CLI:

```bash
python -m ailuros --help
python -m ailuros version
```

Validate the refund policy file:

```bash
python -m ailuros policy validate examples/refund_agent/policies/refund.json
```

Run the refund demo:

```bash
python examples/refund_agent/main.py
```

The demo writes to `ailuros.sqlite` by default and prints a `run_id`. Use that id with the inspection commands:

```bash
python -m ailuros run list
python -m ailuros run show <run_id>
python -m ailuros replay <run_id>
python -m ailuros audit <run_id>
python -m ailuros eval <run_id> --case examples/refund_agent/evaluation/high_refund_requires_review.json
```

If the database is somewhere else, pass it before the command:

```bash
python -m ailuros --db path/to/ailuros.sqlite run show <run_id>
```

Run the minimal hello governance demo:

```bash
python examples/hello.py
```

The hello demo uses an in-memory database and prints the five governance artifacts directly: decision, ordered events, run summary, replay timeline, and audit summary. No external files, network, or API keys required.

## Refund demo behavior

The refund demo starts a local run, records an order status result, then attempts `payment.issue_refund` through `runtime.wrap_tool`. The sample policy requires review for the high-value refund, so the runtime records a blocking governance decision and the refund function is not called.

After the blocked attempt, the demo calls `runtime.validate_path` with an expected path requiring `payment.issue_refund`. That path validation result is written to the run timeline and can be seen with `run show`, `replay`, or `audit`.

## Validation

Run the current repository checks with:

```bash
python -m ruff check .
python -m pytest -q
python -m mypy src
```

## Not implemented in v0.1

The current repository does not implement a server, framework-specific adapters (LangChain, LlamaIndex, etc.), regression comparison workflows, or a full documentation site. A framework-neutral adapter contract skeleton (`src/ailuros/adapters/`) is in place with a reference `LocalCallableAdapter` that validates blocked calls never reach underlying tools. Some model names may exist as public data types, but this README only treats the runtime kernel, policy gate, path validation, stored timelines, audit/replay/eval CLI, refund demo, and adapter contract boundary as implemented behavior.

## Product Line &amp; Strategy

Ailuros is the canonical governance runtime. See the canonical docs for strategy,
architecture, and decisions:

- **Strategy:** [Product Line Thesis](docs/strategy/product-line-thesis.md) ·
  [Reference Apps](docs/strategy/reference-apps.md) ·
  [Roadmap](docs/strategy/roadmap.md)
- **Architecture:** [Governance Boundary](docs/architecture/governance-boundary.md) ·
  [Clarify Reference Application](docs/architecture/clarify-reference-app.md)
- **Decisions:** [ADR-0001](docs/decisions/ADR-0001-ailuros-as-governance-runtime.md) ·
  [ADR-0002](docs/decisions/ADR-0002-clarify-as-reference-app.md) ·
  [ADR-0003](docs/decisions/ADR-0003-evidence-first-integration.md)
