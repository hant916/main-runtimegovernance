# EverRun Dogfood Data Flow

EverRun is a reference application and proof path for automated agent-run
governance. This document describes the data flow from EverRun execution through
Ailuros governance interpretation to Console presentation, for the MVP dogfood
phase.

## Ownership Model

Three components own distinct concerns. No component crosses into another's
territory.

| Component | Owns | Does Not Own |
|---|---|---|
| **EverRun** | Execution truth: what happened, when, in what order, with what outcome. EverRun is the authoritative recorder of agent tool calls, results, and errors. | Governance interpretation, policy evaluation, status classification, report rendering. |
| **Ailuros** | Governance interpretation: evidence ingestion, contract validation, deterministic projection, policy evaluation, pass/warn/fail decisions, audit trails. | Execution recording, UI rendering, presentation logic. |
| **Console** | Presentation only: rendering reports, surfacing problems, displaying status. Console reads from Ailuros outputs and adds no governance logic. | Evidence ingestion, policy evaluation, status classification, evidence validation. |

EverRun sends evidence to Ailuros. Ailuros produces governance signals. Console
renders them. The dependency graph is one-way: EverRun → Ailuros → Console.

## Data Levels

Evidence flows through five levels from raw capture to user-facing report.
Derived levels (3–5) are deterministic and rebuildable from levels 1–2.

| Level | Name | Owner | Description | Rebuildable |
|---|---|---|---|---|
| 1 | Raw Package | EverRun | Canonical execution evidence bundle produced after a run completes. Contains timeline events, tool call records, results, and errors exactly as they occurred. | Source of truth |
| 2 | Stored Evidence | Ailuros | Raw package loaded, validated against the evidence contract, and stored as opaque `EvidenceRecord` entries in the Ailuros timeline. Payloads are preserved uninterpreted. | No (persisted once) |
| 3 | ExecutionProjection | Ailuros | Deterministic projection from stored evidence into execution-level facts: tool calls made, sequence ordering, outcomes, errors. Derived mechanically from level 2. | Yes |
| 4 | GovernanceSignal | Ailuros | Contract validation result, audit decision (pass/warn/fail), and policy evaluation outcomes produced from the projection. | Yes |
| 5 | Report / Overview / Problems | Console | Human-readable rendering of governance signals: summary status, problem list, evidence drill-down links. No new governance logic. | Yes |

Levels 3–5 are rebuildable. Given the same raw package, re-running the Ailuros
pipeline produces identical governance signals. Console re-rendering from those
signals produces identical reports.

## MVP Flow

The MVP phase implements post-run import only. Realtime event ingestion and
distributed platform infrastructure are deferred.

### Implemented (MVP)

```
EverRun Run Completes
        │
        ▼
  Raw Package (on disk)
        │
        ▼
  Ailuros Post-Run Import ──► Stored Evidence
        │
        ▼
  ExecutionProjection (deterministic)
        │
        ▼
  GovernanceSignal (audit decision, warnings, errors)
        │
        ▼
  Console Report / Problem List
```

1. EverRun completes an agent run and writes a canonical evidence package to
   disk.
2. Ailuros loads the package via `load_evidence_package`, validates it against
   the evidence contract via `validate_evidence_package_contract`, and stores
   the validated events.
3. The stored evidence is deterministically projected into an
   `ExecutionProjection`: a machine-readable summary of what executed.
4. Ailuros produces a `GovernanceSignal`: an `AuditResult` with a
   pass/warn/fail decision derived from contract validation.
5. Console renders the signal as a report with problems and evidence drill-down
   links.

### Deferred (Not in MVP)

| Feature | Reason |
|---|---|
| Realtime event ingestion | Requires a streaming interface or HTTP API; Ailuros is in-process only. |
| Distributed platform infrastructure | Out of scope for local runtime kernel; Phase 5 concern. |
| Live tool call gating from EverRun events | No runtime control surface back to EverRun. |
| Multi-run aggregation | MVP handles one run at a time. |
| Historical trend analysis | Requires persistent aggregation layer; deferred. |

## Traceability Rule

Every negative or warning status shown to users must be traceable to specific
evidence. LLM analysis must be visually and semantically separated from
observed evidence.

### Evidence References

- Every warning and error in a `GovernanceSignal` carries a reference to the
  source evidence record (run_id, event sequence, or contract rule violated).
- Console must render these references as navigable links or identifiers so
  users can drill down from a problem to the underlying evidence.
- A problem without an evidence reference is a rendering defect.

### LLM Analysis Separation

- LLM-generated summaries, interpretations, or recommendations are **analysis**,
  not evidence.
- In reports, analysis is rendered in a visually distinct block (separate
  section, distinct formatting, or explicitly labeled as "Analysis").
- Evidence (timeline events, validation results, contract violations) is
  rendered in a separate block labeled "Evidence" or "Observed".
- No governance decision is derived from LLM analysis; decisions must cite
  contract rules and observed evidence only.

## Boundary Guard

The governance boundary defined in `docs/architecture/governance-boundary.md`
applies. Specifically for EverRun:

- Ailuros core (`src/ailuros/`) never imports EverRun concepts or modules.
- EverRun-specific event types (e.g. `everrun.execution.tool_call`) are
  free-form strings in `EvidenceRecord.event_type`; they are not defined as
  Python types in `src/ailuros/`.
- Console rendering logic for EverRun reports lives in the Console or EverRun
  repository, not in `src/ailuros/`.
- No reference-app concept enters Ailuros core.

## Related Documents

- [Governance Boundary](governance-boundary.md)
- [Product Line Thesis](../strategy/product-line-thesis.md)
- [Phase 1 Dogfood](../strategy/phase1-dogfood.md)
- [Evidence Package Post-Run Governance Contract v1.5](../contracts/evidence-package-post-run-governance-v15.md)
- [Phase 1 Evidence-Only Contract](../contracts/phase1-evidence-only-contract.md)
- [Clarify Reference Architecture](clarify-reference-architecture.md)
