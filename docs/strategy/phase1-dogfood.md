# Phase 1 Dogfood: Reference App Fixtures

**Date:** 2026-06-04
**Scope:** Demonstrate reference apps as EvidenceRecord consumers

## One Core, Three Proofs

Ailuros provides a single governance runtime core (`src/ailuros/`). Three reference
applications consume it as evidence producers. None of them is a core dependency.

```
┌─────────────────────────────────────────────────┐
│              Ailuros (Core Governance Runtime)   │
│  EvidenceRecord · ingest · export · evaluation   │
└──────┬──────────┬──────────┬────────────────────┘
       │          │          │
       ▼          ▼          ▼
   Clarify    EverRun   radarCreation
  (browser)  (agents)    (domain)
```

## Consumer Relationship

| Reference App | Evidence Event Type | Dogfood Fixture |
|---|---|---|
| Clarify | `clarify.browser.navigation` | `examples/reference_apps/fixtures/clarify_browser.json` |
| EverRun | `everrun.execution.tool_call` | `examples/reference_apps/fixtures/everrun_execution.json` |
| radarCreation | `radarCreation.risk.assessment` | `examples/reference_apps/fixtures/radarcreation_risk.json` |

Each fixture is a standalone `EvidenceRecord` that validates against the generic
evidence contract only. No payload-domain schema is required by core.

## Contract Validation

Tests in `tests/test_reference_app_fixtures.py` validate:

- Each fixture is a valid `EvidenceRecord` (required fields, types, timezone-aware timestamp)
- Payloads are preserved opaquely; core never inspects payload internals
- Extra top-level fields are rejected (`extra="forbid"`)
- Event types are free-form strings, not restricted to the core runtime enum
- JSON round-trip preserves identity

No fixture requires Clarify, EverRun, or radarCreation to be present as a core
module. The fixtures are read from disk and validated through the generic
`EvidenceRecord` Pydantic model only.

## Boundary Guard

The boundary guard in `tests/test_core_boundary.py` ensures that no reference-app
terms (clarify, browser, sidepanel, cta) appear in `src/ailuros/`. The dogfood
fixtures live entirely outside that boundary in `examples/reference_apps/`.

## Related Documents

- [Product Line Thesis: One Core, Three Proofs](product-line-thesis.md)
- [Reference Applications](reference-apps.md)
- [Phase 1 Readiness](phase1-readiness.md)
- [Phase 1 Evidence-Only Contract](../contracts/phase1-evidence-only-contract.md)
