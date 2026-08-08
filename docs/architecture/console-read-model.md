# Console Read Model: Ailuros Console Boundary

This document defines the application boundary, screens, data ownership, and MVP
technical choices for the Ailuros console (`apps/console`). The console is a
read-only client of Ailuros core APIs. It owns no runtime logic, no status
inference, and no write paths.

## Application Boundary

| Concern | Location | Notes |
|---|---|---|
| Console UI | `apps/console` | Static HTML/CSS/JS; no framework required |
| Core domain | `src/ailuros/` | Runtime lifecycle, policy, storage, CLI |
| UI modules in core | Forbidden | No UI components, DOM concepts, or browser APIs in `src/ailuros/` |

The dependency graph is one-way: `apps/console` imports types and calls read APIs
exposed by Ailuros core. Ailuros core never imports from the console.

## Screens

### Overview
Dashboard showing aggregate run statistics, recent activity, and high-level
governance posture. Links into Runs and Problems.

### Runs
List view with filtering and sorting. Columns: run ID, start time, outcome,
trigger type, policy version. Each row links to Run Detail.

### Run Detail
Single-run view with the following sections:

| Section | Contents |
|---|---|
| Outcome | Overall pass/fail/blocked status, summary message |
| Timeline | Ordered tool invocations with timestamps |
| Governance | Policy rules evaluated, decisions rendered |
| Validation | Path and manifest validation results |
| Changes | File modifications recorded during the run |
| Runtime | Environment, model, duration, token usage |
| Evidence | Links to persisted evidence packages and audit reports |

### Problems
List of runs that resulted in blocked or failed governance decisions, with
links to the relevant Run Detail section.

## Data Ownership

| Rule | Description |
|---|---|
| Read-only DTOs | Console fetches read API DTOs exposed by Ailuros core. No console-side data mutation. |
| No status inference | All status values (pass, fail, blocked) come from core DTOs. JavaScript computes no status. |
| No write API | Console calls no POST, PUT, or DELETE endpoints. Core owns all mutation. |
| No local state derivation | Console renders what the API returns; it does not derive governance conclusions client-side. |

## API Read Model (DTOs)

The console consumes the following logical DTOs. The exact wire format is
determined by core's read API layer and is not defined here.

- **RunSummary**: id, started_at, completed_at, outcome, trigger, policy_version
- **RunDetail**: RunSummary fields plus timeline, governance_decisions,
  validation_results, changes, runtime_info, evidence_links
- **Problem**: id, run_id, rule_violated, severity, timestamp, detail_link
- **OverviewStats**: total_runs, passed, failed, blocked, recent_runs (list of
  RunSummary)

## MVP Technical Choice

- **Static HTML/CSS/JS** served from `apps/console/` via a simple file server
  or dev hosting (e.g., `python -m http.server`).
- **No Node framework** required. No build step, no bundler, no package manager
  unless future repository evidence proves need.
- **API integration** via `fetch()` against the Ailuros read API endpoint
  (host and port configurable, defaults TBD by core API layer).

## Cross-Cutting Rules

1. Console introduces no new Python packages or changes to `src/ailuros/`.
2. Console must not embed policy evaluation, governance decision logic, or
   runtime lifecycle management.
3. Console styling is implementation-detail; this document prescribes no CSS
   framework, design system, or component library.
4. Console must degrade gracefully when the read API is unreachable (show error
   state, not stack traces).
