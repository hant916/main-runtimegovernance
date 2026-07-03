# Ailuros Clarify Evidence Validation Report

## Status

PASS

## Summary

- Source: clarify
- Run ID: clarify-run-sample-0005
- Timeline events: 6
- Clarify validation: passed
- Blocking issues: 0
- Warnings: 0

## Checks

| Level | Check | Status | Message |
|---|---|---|---|
| P0 | bundle_dir_exists | PASS | bundle directory exists |
| P0 | manifest_exists | PASS | manifest.json exists |
| P0 | manifest_valid_json | PASS | manifest.json is valid JSON |
| P0 | manifest_schema_version | PASS | manifest schema_version is valid |
| P0 | manifest_producer | PASS | manifest producer is clarify |
| P0 | manifest_artifacts | PASS | manifest.artifacts is present |
| P0 | manifest_artifacts_exist | PASS | all manifest artifacts exist |
| P0 | timeline_exists | PASS | ailuros.timeline.v0.json exists |
| P0 | clarify_validation_result_exists | PASS | clarify-validation-result.json exists |
| P1 | manifest_bundle_type | PASS | manifest bundle_type is valid |
| P1 | manifest_runtime_integration | PASS | manifest.runtime_integration is false |
| P1 | manifest_run_id | PASS | manifest.run_id is present |
| P1 | manifest_created_at | PASS | manifest.created_at is present |
| P1 | timeline_valid_json | PASS | timeline JSON is valid |
| P1 | timeline_schema_version | PASS | timeline schema_version is valid |
| P1 | timeline_run_id | PASS | timeline.run_id is present |
| P1 | timeline_created_at | PASS | timeline.created_at is present |
| P1 | timeline_events_array | PASS | timeline.events is an array |
| P1 | timeline_events_count | PASS | timeline has 6 events |
| P1 | timeline_event_order | PASS | timeline event order is valid |
| P1 | timeline_event_0_contract | PASS | events[0] has required fields |
| P1 | timeline_event_1_contract | PASS | events[1] has required fields |
| P1 | timeline_event_2_contract | PASS | events[2] has required fields |
| P1 | timeline_event_3_contract | PASS | events[3] has required fields |
| P1 | timeline_event_4_contract | PASS | events[4] has required fields |
| P1 | timeline_event_5_contract | PASS | events[5] has required fields |
| P1 | quality_signals_present | PASS | quality_signals is present |
| P1 | quality_signals_required_fields | PASS | quality_signals has required fields |
| P1 | quality_signals_boolean | PASS | quality_signals are boolean |
| P1 | clarify_validation_valid_json | PASS | clarify validation result JSON is valid |
| P1 | clarify_validation_schema_version | PASS | clarify schema_version is valid |
| P1 | clarify_validation_status | PASS | clarify validation passed |
| P1 | clarify_validation_commands | PASS | clarify commands is an array |
| P1 | clarify_validation_passed_commands | PASS | passed clarify validation commands passed |
| P1 | evidence_only_forbidden_keys | PASS | no forbidden runtime or policy keys found |
| P2 | secret_like_keys | PASS | no suspicious secret-like keys found |
| P2 | local_path_references | PASS | no local machine path references found |

## Boundary

- Offline validation only
- No HTTP ingestion
- No runtime policy execution
- No blocking / approval / human-review action
