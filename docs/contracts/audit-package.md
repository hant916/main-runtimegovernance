# Audit Package Contract

## Scope

The audit package is a read-only local export that packages timeline, decisions,
evidence, validation summary, and replay metadata for human review. It is
generated from observable stored artifacts only.

## Package structure (version 1)

```json
{
  "audit_package_version": "1",
  "run_id": "<string>",
  "generated_at": "<ISO 8601 timestamp>",
  "run": {
    "agent_id": "<string>",
    "environment": "<development|staging|production>",
    "status": "<running|completed|failed|blocked>",
    "created_at": "<ISO 8601>",
    "updated_at": "<ISO 8601>"
  },
  "summary": {
    "decision": "<allow|warn|sanitize|require_review|block|unknown>",
    "reason": "<string>",
    "tool": "<string>",
    "path_validation": "<valid|invalid|absent|unknown>",
    "event_count": <int>,
    "decision_counts": { "<decision_type>": <int>, ... },
    "blocked_count": <int>,
    "review_count": <int>
  },
  "timeline": [
    {
      "event_id": "<string>",
      "event_type": "<RuntimeEventType value>",
      "timestamp": "<ISO 8601>",
      "sequence": <int|null>
    },
    ...
  ],
  "decisions": [
    {
      "event_id": "<string>",
      "timestamp": "<ISO 8601>",
      "sequence": <int|null>,
      "decision": "<string>",
      "reason": "<string>",
      "...": "<decision payload fields>"
    },
    ...
  ],
  "evidence": [
    {
      "event_id": "<string>",
      "run_id": "<string>",
      "event_type": "<string>",
      "timestamp": "<ISO 8601>",
      "sequence": <int|null>,
      "evidence": { "version": "<string>", "event_type": "<string>", "payload": {} }
    },
    ...
  ],
  "validation": {
    "path_validations": [
      {
        "event_id": "<string>",
        "timestamp": "<ISO 8601>",
        "sequence": <int|null>,
        "valid": <bool>,
        "path_id": "<string>"
      },
      ...
    ]
  },
  "replay": {
    "replay_runs": [
      {
        "replay_id": "<string>",
        "run_id": "<string>",
        "status": "<string>",
        "created_at": "<ISO 8601>",
        "key_events": [],
        "metadata": {}
      },
      ...
    ]
  } | null
}
```

## Invariants

1. **Read-only**: The export does not mutate the storage or stored runs.
2. **Observable artifacts only**: All data comes from stored events, decisions,
   evidence records, or replay results. No hidden state or model internals are
   recomputed.
3. **No secrets**: The package does not include chain-of-thought, model
   internals, or private runtime state.
4. **Deterministic ordering**: JSON output uses `sort_keys=True` for
   deterministic serialization. Timeline, decisions, and evidence are ordered
   by sequence number ascending.

## CLI usage

```
ailuros audit-package <run_id> [--db <path>]
```

Outputs the audit package as JSON to stdout.

## API

```python
from ailuros.audit import export_audit_package, export_audit_package_json

# Returns dict
package = export_audit_package(storage, run_id)

# Returns JSON string
json_str = export_audit_package_json(storage, run_id)
```

## Exclusions

- Does not include raw logs, runtime history, or execution state.
- Does not call external services.
- Does not add server write behavior.
- Replay section is `null` when no replay results exist for the run.
