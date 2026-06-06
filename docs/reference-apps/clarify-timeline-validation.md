# Clarify Timeline v0 Validation

## Provenance

The Clarify-generated `examples/ailuros/clarify_timeline_v0.sample.json` artifact was
located in the Clarify repository handoff. The sample is a minimal, deterministic
timeline with six mandatory event types covering the full evidence lifecycle.

The golden fixture at `examples/reference_apps/fixtures/clarify_timeline_v0.json` is
a direct copy of the Clarify-generated sample. It is kept minimal, deterministic, and
sanitized. No raw logs, execution history, or `.everrun` artifacts were imported.

## Fixture Location

`examples/reference_apps/fixtures/clarify_timeline_v0.json`

## Contract Validation

Ailuros validates Clarify timeline fixtures at the **evidence-contract level only**:

- **Schema version**: validated as `"ailuros.timeline.v0"` by `clarify_timeline_contract.py`
- **Required event types**: `INPUT_CLASSIFIED`, `LLM_REQUEST`, `LLM_RESPONSE`,
  `EVALUATION_RESULT`, `OUTPUT_GENERATED`, `RUN_COMPLETED`
- **Minimal required fields per event**: `event`, `run_id`, `timestamp`
- **Safe fixture constraints**: events must be a non-empty array of objects; each
  event must carry the mandatory string fields

The contract module is located at `src/ailuros/adapters/clarify_timeline_contract.py`.
All Clarify-specific validation logic is restricted to `adapters/`.

## Compatibility Result

Ailuros validates Clarify as a reference app at the **evidence-contract level only**.

### Explicitly Included

- Evidence contract validation (schema_version, event types, required fields)
- Golden fixture import and validation
- Focused tests verifying fixture acceptance and rejection of invalid content
- Script-based fixture check (`scripts/check_clarify_reference_app_fixture.py`)

### Explicitly Excluded

| Feature | Status | Rationale |
|---|---|---|
| Runtime browser adapter | Excluded | No browser adapter implementation |
| HTTP transport layer | Excluded | No HTTP endpoint or transport layer |
| Database persistence | Excluded | No database persistence for Clarify data |
| Policy engine callback | Excluded | No policy engine or runtime governance decision return path |
| Core boundary weakening | Excluded | Core remains reference-app-agnostic |

## Validation Commands

```bash
python -m pytest tests/test_clarify_reference_timeline_fixture.py -q
python scripts/check_clarify_reference_app_fixture.py
```

## Reference

- `docs/architecture/clarify-reference-app.md` — Clarify reference architecture
- `docs/architecture/governance-boundary.md` — Core/reference-app boundary definition
- `src/ailuros/adapters/clarify_contract.py` — ClarifyGovernanceRequest model
- `src/ailuros/adapters/clarify_timeline_contract.py` — Timeline contract validation
