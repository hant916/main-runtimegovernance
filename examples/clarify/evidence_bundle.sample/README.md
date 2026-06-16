# Clarify Evidence Bundle Sample

A minimal valid Clarify evidence bundle for offline validation testing.

## Contents

- `manifest.json` — bundle manifest (schema_version: ailuros.evidence_bundle.v0, producer: clarify)
- `ailuros.timeline.v0.json` — Ailuros timeline with 6 events and quality_signals
- `clarify-validation-result.json` — Clarify's own validation result (status: passed)
- `clarify-validation.log` — Clarify's validation log

## Usage

```bash
python scripts/validate_clarify_evidence_bundle.py --bundle examples/clarify/evidence_bundle.sample
```

Expected result: PASS (exit code 0)
