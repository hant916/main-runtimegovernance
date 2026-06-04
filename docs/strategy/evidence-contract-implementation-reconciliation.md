# Evidence Contract Implementation Reconciliation

**Task ID:** 0073.evidence-contract-implementation-reconciliation
**Date:** 2026-06-04
**Status:** reconciliation-complete

## Classification

| Question | Answer | Evidence |
|---|---|---|
| Does EvidenceRecord or equivalent source model exist? | **Yes** | `src/ailuros/models/evidence.py:7-21` — full Pydantic BaseModel with 5 fields |
| Is it exported from the package? | **Yes** | `src/ailuros/models/__init__.py:6` and `src/ailuros/__init__.py:16` |
| Do tests import the real source model? | **Yes** | Both test files use `from ailuros import EvidenceRecord` |
| Is the contract test-only? | **No** | Source model file exists and is imported by tests |
| Is the contract doc-only? | **No** | Source model file exists and is imported by tests |

**Overall state: IMPLEMENTED**

The generic `EvidenceRecord` contract model is fully implemented in source, exported from the `ailuros` package, and covered by passing tests. No implementation gap exists for the model itself.

## Evidence Record Source Model

**File:** `src/ailuros/models/evidence.py`
**Lines:** 21
**Class:** `EvidenceRecord(BaseModel)`

| Field | Type | Default | Matches Contract |
|---|---|---|---|
| `version` | `str` | required | Yes |
| `run_id` | `str` | required | Yes |
| `event_type` | `str` | required | Yes |
| `payload` | `dict[str, Any]` | `{}` | Yes |
| `timestamp` | `datetime` | required | Yes |
| `model_config` | `ConfigDict(extra="forbid")` | — | Yes |
| Timezone validator | `field_validator("timestamp")` | — | Yes |

**Exports:**
- `src/ailuros/models/__init__.py` — `EvidenceRecord` in `__all__`
- `src/ailuros/__init__.py` — `EvidenceRecord` in `__all__`

## Contract Test Coverage

| Test File | Lines | Tests | Import Source | Status |
|---|---|---|---|---|
| `tests/test_evidence_record_contract.py` | 129 | 11 | `from ailuros import EvidenceRecord` (line 6) | All pass |
| `tests/test_evidence_contract.py` | 147 | 15 | `from ailuros import EvidenceRecord` (line 6) | All pass |

**Test areas covered:**
- Required field validation (version, run_id, event_type, timestamp)
- Extra field rejection (`extra="forbid"`)
- Naive datetime rejection (timezone enforcement)
- Payload preservation (opaque, arbitrary nested structures)
- Payload defaults to empty dict
- No domain-specific fields (`browser`, `dom`, `sidepanel`, `cta`, `supplier`, `kyb`, `radarCreation`)
- Event type is free-form string (not restricted to `RuntimeEventType`)
- Application-neutral field set
- JSON round-trip serialization

## Known Discrepancies

| # | Description | Severity | Details |
|---|---|---|---|
| D1 | Roadmap references `test_evidence_contract.py` (147 lines) but contract doc references `test_evidence_record_contract.py` (129 lines) | Low | Both files exist and pass. The roadmap predates the rename/split. No functional gap. |
| D2 | `phase1-readiness.md` still lists evidence ingestion/export/evaluation as `[ ]` deferred items, but source confirms they are implemented (packs 0070–0072 COMPLETE) | Low | Document drift. Roadmap already records this contradiction at lines 200-206 of `evidence-roadmap-v0.2.md`. |
| D3 | Evidence ingest, export, evaluation, and regression modules exist and are tested beyond the model contract scope | Informational | These were implemented by packs 0070–0072. This reconciliation focuses on the model contract only; the presence of ingest/export/eval is noted but is not a gap. |

## What is Beyond Scope (already implemented, not part of this reconciliation)

These source files exist and are tested, per the roadmap's declaration that packs 0070–0072 are COMPLETE:

- `src/ailuros/evidence/ingest.py` — `ingest_evidence()` stores evidence as timeline event
- `src/ailuros/evidence/export.py` — `export_evidence()`, JSON/JSONL export
- `tests/test_evidence_ingest.py` — 165 lines, 2 test classes
- `tests/test_evidence_export.py` — 218 lines, 5 test classes
- `tests/test_evidence_evaluation.py` — 362 lines, 5 test classes
- `tests/test_evidence_regression.py` — 300 lines, 9 test classes

These are acknowledged but are not within this reconciliation's scope. The model contract gap is the focus, and it is closed.

## Recommendation

**Next pack: v0.2.0 Release Verification (as originally scheduled in roadmap line 86)**

The evidence contract model is implemented. Packs 0070–0072 (model, ingest, export) are implemented and tested. The remaining work is formal release verification:
- Run `scripts/check_release_v020.py`
- Run `tests/test_release_v020.py`
- Create `docs/release/v0.2.0-readiness.md`
- Flip `docs/release/v0.2.0-acceptance.md` status from "acceptance-defined" to "acceptance-passed"

**No "implement model" pack is needed.** The model is source-implemented, exported, and test-covered.

## Unknowns (explicitly recorded)

| Item | Status |
|---|---|
| Task 0055 satisfaction | Unknown — no reference found in repository files (recorded in `docs/strategy/ailuros-run-reconciliation.md` line 116). Does not block evidence work. |
| Planner/judge ACCEPT | Cannot verify — run evidence reports `planner_unavailable` and `judge_not_invoked`. |

## Scope Verification

| Red Line | Status |
|---|---|
| No evidence ingest implementation | Compliant — no new ingest code added |
| No export implementation | Compliant — no new export code added |
| No evaluation/regression implementation | Compliant — no new eval/regression code added |
| No server write API | Compliant — no server code modified |
| No domain-specific concepts in src/ailuros | Compliant — no src/ailuros files modified |
| No source files modified | Compliant — only this doc created |

## Files Created

| File | Purpose |
|---|---|
| `docs/strategy/evidence-contract-implementation-reconciliation.md` | This reconciliation report |
