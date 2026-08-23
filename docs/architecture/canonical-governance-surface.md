# Canonical Governance Surface

Evidence-backed ownership map for the Ailuros governance surface. This document is
the freeze point for *which module owns which governance semantics*. It exists to
prevent future duplicate semantic ownership: when two modules claim the same concept,
they drift, and governance behavior becomes ambiguous.

The authoritative execution-boundary contract (scope ownership, external boundary
surfaces, product ownership matrix, temporal invariants) remains
[governed-execution-scope-v1.md](../contracts/governed-execution-scope-v1.md).
This document is the internal, module-level mapping that supplements it and
[governance-boundary.md](./governance-boundary.md).

Status of each entry is one of:
`canonical` (single owner, may be depended on), `facade` (thin re-export or packaging
wrapper over a canonical owner), `dead duplicate` (shadowed / unreachable, must not be
extended or imported), or `reference-app` (sanctioned home for a specific reference
application contract).

## 1. Overlapping Surfaces Inventory

The word "audit", "regression", and "evidence" each appear on more than one module.
Each cluster below is resolved to a single canonical owner; the rest are facades or
dead duplicates.

### 1.1 Audit surface

| Module | Role | Ownership |
|---|---|---|
| `src/ailuros/core/audit.py` | Post-run evidence-package verdict: `AuditDecision` (pass/warn/fail), `AuditResult`. Explicitly *not* runtime control. | **canonical** |
| `src/ailuros/core/report.py` | `render_audit_markdown` — deterministic Markdown for `AuditResult`. | **canonical** (renderer of `core/audit.py`) |
| `src/ailuros/audit/summary.py` | Run-level summary over runtime `GOVERNANCE_DECISION` events: `AuditSummary`, `RunSummary`, `build_audit_report` (JSON dict). Different concept from `core/audit.py` (runtime decision string vs pass/warn/fail verdict). | **canonical** |
| `src/ailuros/audit/__init__.py` | Re-exports `audit.summary` and `audit.package_export`. | facade |
| `src/ailuros/audit/package_export.py` | JSON audit-package export composed from `audit.summary` + storage. | facade (over `audit.summary`) |
| `src/ailuros/audit_package/` | Directory-based audit package export / load / validate / decide; depends on `audit.summary`. | facade (over `audit.summary` + package verification) |
| `src/ailuros/adapters/evidence_package/{audit,rules,json_report,markdown_report}.py` | Evidence-package audit via `core/audit.py` verdict types. | facade (adapter over `core/audit.py`) |

Governance semantics red line: the pass/warn/fail verdict is owned **only** by
`core/audit.py`; the runtime allow/warn/sanitize/require_review/block decision string
is owned **only** by the decision layer (`policy/decision_resolver.py`, `runtime/runtime.py`)
and read by `audit/summary.py`. Neither may start re-deriving the other.

### 1.2 Regression surface

| Module | Role | Ownership |
|---|---|---|
| `src/ailuros/regression/` (package) | Canonical regression surface: `governance_delta.py` (source-neutral governance deltas), `service.py` (case-based regression), `timeline.py` (timeline replay validation), `models.py`. | **canonical** |
| `src/ailuros/regression/governance_delta.py` | `compare_governance_projections`, `GovernanceDimension`, `GovernanceTransition`, deltas. | **canonical** (imported via `regression/__init__.py`) |
| `src/ailuros/regression.py` (module) | Byte-for-byte near-copy of `regression/governance_delta.py`. Python resolves `import ailuros.regression` to the package (FileFinder prefers the directory with `__init__`); the module is shadowed, unreachable, and **imported by no source file**. | **dead duplicate** (do not extend, do not delete solely for overlap; see red line) |
| `src/ailuros/models/regression.py` | `RegressionComparisonResult` (legacy shape) exported via `models/__init__.py` and `ailuros/__init__.py` but never constructed anywhere. | **dead duplicate** (legacy export; live shape is `regression/models.py`) |

Red line: `regression/governance_delta.py` is the single owner of governance-delta
semantics. Do not add new importers of the shadowed `regression.py` module, and do not
give `models/regression.py` a second live producer while `regression/models.py` exists.

### 1.3 Evidence surface

| Module | Role | Ownership |
|---|---|---|
| `src/ailuros/evidence/` | Internal run-evidence ingest/export over `models/evidence.py` (`EvidenceRecord`) and storage events. | **canonical** (internal evidence) |
| `src/ailuros/core/evidence.py` | Canonical interchange models: `Provenance`, `PackageMetadata`, `EvidenceEvent`, `EvidencePackage`. | **canonical** (evidence-package interchange) |
| `src/ailuros/adapters/evidence_package/` | Load / validate / ingest / audit external evidence packages against `core/evidence.py`, `core/validation.py`, `core/audit.py`. | facade (adapter over `core/*`) |
| `src/ailuros/models/evidence.py` | `EvidenceRecord` — internal event-record form. | canonical (internal evidence record) |

Red line: interchange semantics live in `core/evidence.py`; internal event-record
semantics live in `models/evidence.py`. The two shapes are different by design and must
not be merged or re-implemented in the other location.

## 2. Dependency Direction (proven import graph)

Verified import direction (no reverse edges observed):

```
core/            (leaf: imports only ailuros._compat and ailuros.core.*)
   ↑
projection.py    (imports core.execution; local import of signals in rebuild)
signals.py       (imports core.execution, models.common)
   ↑
execution_report.py  (imports core.execution, projection, signals)
   ↑
cli.py / server/app.py / backfill.py
```

Runtime layer is independent of the projection stack:
`runtime/runtime.py` imports `models`, `path`, `policy`, `runtime.*`, `storage`,
`errors` — it does **not** import projection/signals/execution_report. Projection is
rebuilt downstream from stored events.

Decision-making red line: live governance decision-making is owned by
`policy/engine.py` + `policy/decision_resolver.py`, orchestrated by
`runtime/runtime.py`. `core/execution.py` and `projection.py` are post-run read-models;
they must never start producing decisions, only projecting them.

## 3. Recorded Red Lines

1. **`core/` is a leaf.** Nothing under `src/ailuros/core/` may import packages outside
   `ailuros.core` and `ailuros._compat` (enforced by `tests/test_core_boundary.py` →
   `test_core_is_a_leaf_dependency_root`). Downstream surfaces depend on `core`, never
   the reverse. This prevents the canonical vocabulary from being re-expressed in a
   dependent layer and re-imported (duplicate semantic ownership).
2. **No reference-app imports into core.** Reference-app concepts (e.g. `clarify`,
   `browser`, `sidepanel`, `cta`) are allowed only under `src/ailuros/adapters/`
   (enforced by `tests/test_core_boundary.py` → `test_no_reference_app_terms_in_core`).
3. **Server is read-only.** No HTTP write handlers under `src/ailuros/server/`
   (enforced by `tests/test_core_boundary.py` → `test_server_is_read_only`).
4. **Verdict semantics are single-owner.** `core/audit.py` owns pass/warn/fail;
   `policy/decision_resolver.py` + `runtime/runtime.py` own allow/require_review/block;
   `audit/summary.py` reads, it does not re-derive.
5. **Regression deltas are single-owner.** `regression/governance_delta.py` is the
   implementation; the shadowed `regression.py` module and the legacy
   `models/regression.py` model must not gain new live importers.
6. **Evidence interchange vs internal evidence stay separate.** `core/evidence.py`
   (interchange) and `evidence/` + `models/evidence.py` (internal) are distinct by
   design.
7. **No new BLOCKED / HUMAN_REVIEW paths.** Governance behavior (blocking, review
   precedence in `policy/decision_resolver.py`, `TOOL_CALL_BLOCKED` emission in
   `runtime/runtime.py`, dormant `HUMAN_REVIEW_REQUESTED` / `HUMAN_REVIEW_COMPLETED`
   event types) is frozen. This audit adds no new enforcement gates and changes no
   governance behavior.

## 4. Enforcement Status

- Enforced by `tests/test_core_boundary.py` today: red lines 1, 2, 3.
- Red lines 4, 5, 6, 7 are documentation-only. They are proven invariants but are not
  cheaply assertable without either coupling the test to file bytes or creating brittle
  string-matching rules; they stay manual review gates per the task scope
  (enforce only proven boundaries; otherwise keep documentation-only).

## 5. Evidence Appendix

- Post-run verdict owned by `core/audit.py` (`AuditDecision` PASS/WARN/FAIL) and
  rendered by `core/report.py`; adapters wrap it
  (`adapters/evidence_package/audit.py`, `rules.py`, `json_report.py`,
  `markdown_report.py`).
- Run summary owned by `audit/summary.py`; consumed by `audit/package_export.py` and
  `audit_package/__init__.py`.
- `import ailuros.regression` resolves to `regression/__init__.py` (package); module
  `regression.py` is shadowed; no source file imports it.
- `regression/models.py:RegressionComparisonResult` is the live shape
  (`regression/service.py`); `models/regression.py` holds the dead legacy shape.
- Runtime emits events (`runtime/runtime.py`); projection/signals/execution_report are
  downstream and depend on `core.execution` + `projection`.