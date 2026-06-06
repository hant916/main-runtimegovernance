# Reference-App Readiness Gate

## Purpose

The reference-app readiness gate verifies that the Ailuros governance runtime
accepts Clarify-timeline-generated evidence-contract fixtures at the schema and
contract level. It does **not** exercise runtime behavior, policy loops, HTTP
transport, database persistence, or browser integrations.

## Definition of Ready

A reference app is **ready** when:

| Condition | Check |
|---|---|
| Golden fixture present | `examples/reference_apps/fixtures/clarify_timeline_v0.json` exists |
| Contract validator present | `src/ailuros/adapters/clarify_timeline_contract.py` exists |
| Fixture passes contract validation | `validate_clarify_timeline()` returns zero errors |

Ailuros accepts the Clarify-generated evidence-contract fixture when all three
conditions are met.

## Definition of Not Ready

The readiness gate intentionally excludes:

| Domain | Status |
|---|---|
| HTTP transport | Not validated — no HTTP endpoint or transport layer check |
| Database persistence | Not validated — no DB connection or schema check |
| Runtime policy engine | Not validated — no policy loop or governance decision check |
| Browser adapter | Not validated — no browser adapter integration check |
| Full integration | Not validated — only evidence-contract fixture acceptance |

## Validation Commands

```bash
python scripts/check_reference_apps.py
python -m pytest tests/test_reference_app_readiness.py -q
```

## Related Documents

- `docs/reference-apps/clarify-timeline-validation.md` — Clarify timeline v0 validation details
- `docs/architecture/clarify-reference-app.md` — Clarify reference architecture
- `docs/architecture/governance-boundary.md` — Core/reference-app boundary definition
