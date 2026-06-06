# ailuros

Ailuros is a Python governance runtime kernel for local agent runs. Current release:
**v0.3.0**.

It provides an in-process runtime, policy-gated tool calls, SQLite-backed timelines,
evidence ingestion/export, replay/audit/evaluation CLI views, and v0.3 audit-package
export for stored governance runs.

## v0.3 Capabilities

- Start and complete local runtime runs.
- Record runtime events to a SQLite timeline.
- Wrap Python tool functions with a policy gate.
- Block wrapped tool calls when a matching policy returns a blocking decision.
- Validate expected tool-call paths against recorded timeline events.
- Ingest external evidence records into the timeline.
- Export stored evidence as JSON or JSONL.
- Inspect stored runs and timelines from the CLI.
- Replay stored timelines without invoking tools.
- Build audit summaries from stored events.
- Evaluate stored timelines against JSON golden cases.
- Compare evaluation and evidence regressions.
- Export v0.3 audit packages from stored runs.
- Run deterministic hello, refund, evidence, and refund-governance demos.

## Quickstart

Use Python 3.12 or newer. From the repository root:

```bash
python -m pip install -e ".[dev]"
python -m ailuros --help
python -m ailuros version
```

Run the current v0.3 refund governance demo:

```bash
python examples/refund_governance_demo.py --output-dir .tmp/audit-packages
```

The demo processes three deterministic refund fixtures:

- low-value valid refund -> `allow`
- high-value valid refund -> `require_review`
- invalid PNR refund -> `block`

It writes a 7-file audit package under `.tmp/audit-packages/<run_id>/`:

```text
manifest.json
run.json
timeline.jsonl
decisions.json
evaluations.json
regressions.json
summary.md
```

## CLI Examples

Validate a policy:

```bash
python -m ailuros policy validate examples/refund_agent/policies/refund.json
```

Run the original local refund demo:

```bash
python examples/refund_agent/main.py
```

Inspect the generated run:

```bash
python -m ailuros run list
python -m ailuros run show <run_id>
python -m ailuros replay <run_id>
python -m ailuros audit <run_id>
python -m ailuros eval <run_id> --case examples/refund_agent/evaluation/high_refund_requires_review.json
python -m ailuros evidence <run_id> --output json
python -m ailuros audit-package <run_id> --output-dir .tmp/audit-packages
```

If the database is somewhere else, pass it before the command:

```bash
python -m ailuros --db path/to/ailuros.sqlite run show <run_id>
```

Run the minimal hello governance demo:

```bash
python examples/hello.py
```

Run the evidence pipeline demo:

```bash
python examples/evidence_demo.py
```

## Governance Flow

```text
agent code
  -> start_run records a run
  -> record_tool_result can add observed tool output
  -> wrap_tool / before_tool_call requests a tool call through the policy gate
  -> policy gate records the governance decision
  -> allowed calls execute the wrapped Python function
  -> blocked calls record the block and do not call the wrapped function
  -> ingest_evidence can add external evidence records
  -> validate_path compares an ExpectedPath with recorded tool-call events
  -> complete_run records final run status and output
  -> replay, audit, eval, evidence, and audit-package read stored timeline data
```

Replay, audit, eval, evidence export, and audit-package export are read-only views over
stored data. Replay does not invoke tools. Audit does not recompute policy.

## Validation

Run the current repository checks with Python 3.12+:

```bash
python scripts/check_release_v020.py
python scripts/check_release_v030.py
python -m ruff check .
python -m mypy src
python -m pytest tests -q
```

## Release Status

- v0.1.0: finalized governance runtime baseline.
- v0.2.0: accepted evidence-only pipeline.
- v0.3.0: accepted audit-package and refund-governance MVP.

## Explicit Non-Goals in v0.3

Ailuros v0.3.0 does not introduce a UI dashboard, server write API, production
Clarify/radarCreation/browser integration, MCP Gateway integration, broad adapter
ecosystem, agent orchestration, or multi-tenant platform.

## Product Line & Strategy

Ailuros is the canonical governance runtime. See the canonical docs for strategy,
architecture, and decisions:

- **Strategy:** [Product Line Thesis](docs/strategy/product-line-thesis.md),
  [Reference Apps](docs/strategy/reference-apps.md), [Roadmap](docs/strategy/roadmap.md)
- **Architecture:** [Governance Boundary](docs/architecture/governance-boundary.md),
  [Clarify Reference Application](docs/architecture/clarify-reference-app.md)
- **Decisions:** [ADR-0001](docs/decisions/ADR-0001-ailuros-as-governance-runtime.md),
  [ADR-0002](docs/decisions/ADR-0002-clarify-as-reference-app.md),
  [ADR-0003](docs/decisions/ADR-0003-evidence-first-integration.md)
