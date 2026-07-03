# Clarify Evidence Bundle Sample

A minimal Clarify-produced evidence bundle for Ailuros offline validation.

## Contents

- `manifest.json`
- `ailuros.timeline.v0.json`
- `clarify-validation.log`
- `clarify-validation-result.json`

## Usage

```bash
python scripts/process_clarify_evidence_data.py --bundle examples/clarify/evidence_bundle.sample
```

Expected result: `PASS` with exit code `0`.
