# Minimal Governance Dogfood Demo

One governed read-only tool call proves the evidence-backed governance
loop end to end: decision, ordered events, run summary, replay timeline,
and audit summary.

## Run

```bash
python -m pytest tests/test_minimal_dogfood_governance_demo.py -v
```

No network, no external services, no API keys.

## What it demonstrates

1. **Start a run** -- `AilurosRuntime.start_run()` records `RUN_STARTED` and `USER_INPUT_RECEIVED` events.
2. **Governed tool call** -- `AilurosRuntime.before_tool_call()` evaluates policies, produces a `GovernanceDecision`, persists it to storage, and records `TOOL_CALL_REQUESTED`, `POLICY_EVALUATION_RESULT`, and `GOVERNANCE_DECISION` events.
3. **Tool execution** -- `AilurosRuntime.after_tool_call()` records `TOOL_CALL_EXECUTED` and `TOOL_RESULT_RECEIVED` events.
4. **Complete run** -- `AilurosRuntime.complete_run()` records `OUTPUT_GENERATED` and `RUN_COMPLETED` events.
5. **Outputs** -- The test asserts all five governance artifacts are connected:
   - `GovernanceDecision` with decision type, reason, and allowed flag.
   - Ordered `RuntimeEvent` list with monotonic sequence numbers.
   - `RunSummary` from `build_run_summary()` with counts.
   - Replay timeline from `ReplayService.build_timeline()`.
   - `AuditSummary` and `AuditReport` from `build_audit_summary()` / `build_audit_report()`.
6. **Cross-reference** -- Every artifact references the same `run_id`.

## Test structure

Single file, one test function, no fixtures other than `tmp_path`.
