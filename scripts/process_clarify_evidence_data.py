from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 1

RESULT_SCHEMA_VERSION = "ailuros.validation_result.v0"
MANIFEST_SCHEMA_VERSION = "ailuros.evidence_bundle.v0"
TIMELINE_SCHEMA_VERSION = "ailuros.timeline.v0"
CLARIFY_RESULT_SCHEMA_VERSION = "clarify.validation_result.v0"

EXPECTED_EVENTS = [
    "INPUT_CLASSIFIED",
    "LLM_REQUEST",
    "LLM_RESPONSE",
    "EVALUATION_RESULT",
    "OUTPUT_GENERATED",
    "RUN_COMPLETED",
]

REQUIRED_QUALITY_SIGNALS = [
    "json_valid",
    "sentence_too_long",
    "contains_direct_advice",
    "contains_decision_pressure",
    "ambiguities_present",
]

FORBIDDEN_KEYS = {
    "policy_decision",
    "approval_status",
    "human_review_required",
    "policy_action",
    "blocking_action",
    "runtime_blocked",
}

SECRET_LIKE_KEYS = {
    "token",
    "password",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
}

LOCAL_PATH_PATTERNS = ("C:\\", "/Users/", ".everrun", "node_modules")
JSON_FILES_TO_SCAN = (
    "manifest.json",
    "ailuros.timeline.v0.json",
    "clarify-validation-result.json",
)


@dataclass(frozen=True)
class Check:
    level: str
    name: str
    status: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }


def _pass(level: str, name: str, message: str) -> Check:
    return Check(level=level, name=name, status="PASS", message=message)


def _fail(level: str, name: str, message: str) -> Check:
    return Check(level=level, name=name, status="FAIL", message=message)


def _warn(level: str, name: str, message: str) -> Check:
    return Check(level=level, name=name, status="WARN", message=message)


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON at line {exc.lineno}"
    except OSError:
        return None, "file could not be read"


def _iter_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_iter_keys(child))
    elif isinstance(value, list):
        for item in value:
            keys.extend(_iter_keys(item))
    return keys


def _json_contains_local_path(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=True)
    return any(pattern in text for pattern in LOCAL_PATH_PATTERNS)


def _status_from_checks(checks: list[Check]) -> str:
    if any(check.status == "FAIL" for check in checks):
        return "FAIL"
    if any(check.status == "WARN" for check in checks):
        return "WARN"
    return "PASS"


def _find_event(events: list[Any], event_name: str) -> dict[str, Any] | None:
    for event in events:
        if isinstance(event, dict) and event.get("event") == event_name:
            return event
    return None


def _validate_manifest(
    bundle_dir: Path, checks: list[Check]
) -> tuple[dict[str, Any] | None, str | None]:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        checks.append(_fail("P0", "manifest_exists", "manifest.json is missing"))
        return None, None
    checks.append(_pass("P0", "manifest_exists", "manifest.json exists"))

    manifest, error = _read_json(manifest_path)
    if error is not None or not isinstance(manifest, dict):
        checks.append(_fail("P0", "manifest_valid_json", "manifest.json is invalid JSON"))
        return None, None
    checks.append(_pass("P0", "manifest_valid_json", "manifest.json is valid JSON"))

    run_id = manifest.get("run_id") if isinstance(manifest.get("run_id"), str) else None

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        checks.append(
            _fail(
                "P0",
                "manifest_schema_version",
                "manifest.schema_version must be ailuros.evidence_bundle.v0",
            )
        )
    else:
        checks.append(
            _pass("P0", "manifest_schema_version", "manifest schema_version is valid")
        )

    if manifest.get("producer") != "clarify":
        checks.append(_fail("P0", "manifest_producer", "manifest.producer must be clarify"))
    else:
        checks.append(_pass("P0", "manifest_producer", "manifest producer is clarify"))

    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, list):
        artifact_paths = artifacts
    elif isinstance(artifacts, dict):
        artifact_paths = list(artifacts.values())
    else:
        artifact_paths = None

    if artifact_paths is None:
        checks.append(_fail("P0", "manifest_artifacts", "manifest.artifacts is missing"))
    else:
        checks.append(_pass("P0", "manifest_artifacts", "manifest.artifacts is present"))
        missing = [
            str(artifact)
            for artifact in artifact_paths
            if not isinstance(artifact, str) or not (bundle_dir / artifact).is_file()
        ]
        if missing:
            checks.append(
                _fail("P0", "manifest_artifacts_exist", "manifest references missing artifact(s)")
            )
        else:
            checks.append(
                _pass("P0", "manifest_artifacts_exist", "all manifest artifacts exist")
            )

    if not (bundle_dir / "ailuros.timeline.v0.json").is_file():
        checks.append(
            _fail("P0", "timeline_exists", "ailuros.timeline.v0.json is missing")
        )
    else:
        checks.append(_pass("P0", "timeline_exists", "ailuros.timeline.v0.json exists"))

    if not (bundle_dir / "clarify-validation-result.json").is_file():
        checks.append(
            _fail(
                "P0",
                "clarify_validation_result_exists",
                "clarify-validation-result.json is missing",
            )
        )
    else:
        checks.append(
            _pass(
                "P0",
                "clarify_validation_result_exists",
                "clarify-validation-result.json exists",
            )
        )

    if manifest.get("bundle_type") != "governance-contract":
        checks.append(
            _fail("P1", "manifest_bundle_type", "manifest.bundle_type must be governance-contract")
        )
    else:
        checks.append(_pass("P1", "manifest_bundle_type", "manifest bundle_type is valid"))

    if manifest.get("runtime_integration") is not False:
        checks.append(
            _fail(
                "P1",
                "manifest_runtime_integration",
                "manifest.runtime_integration must be false",
            )
        )
    else:
        checks.append(
            _pass("P1", "manifest_runtime_integration", "manifest.runtime_integration is false")
        )

    if not manifest.get("run_id"):
        checks.append(_fail("P1", "manifest_run_id", "manifest.run_id is missing"))
    else:
        checks.append(_pass("P1", "manifest_run_id", "manifest.run_id is present"))

    if not manifest.get("created_at"):
        checks.append(_fail("P1", "manifest_created_at", "manifest.created_at is missing"))
    else:
        checks.append(_pass("P1", "manifest_created_at", "manifest.created_at is present"))

    if manifest.get("test_mode") is True:
        checks.append(
            _warn(
                "P1",
                "manifest_test_mode",
                "manifest.test_mode is true; evidence is not production-grade",
            )
        )

    return manifest, run_id


def _validate_timeline(bundle_dir: Path, checks: list[Check]) -> tuple[int, str | None, Any | None]:
    timeline_path = bundle_dir / "ailuros.timeline.v0.json"
    if not timeline_path.is_file():
        return 0, None, None

    timeline, error = _read_json(timeline_path)
    if error is not None or not isinstance(timeline, dict):
        checks.append(_fail("P1", "timeline_valid_json", "timeline JSON is invalid"))
        return 0, None, None
    checks.append(_pass("P1", "timeline_valid_json", "timeline JSON is valid"))

    run_id = timeline.get("run_id") if isinstance(timeline.get("run_id"), str) else None

    if timeline.get("schema_version") != TIMELINE_SCHEMA_VERSION:
        checks.append(
            _fail(
                "P1",
                "timeline_schema_version",
                "timeline.schema_version must be ailuros.timeline.v0",
            )
        )
    else:
        checks.append(_pass("P1", "timeline_schema_version", "timeline schema_version is valid"))

    if not timeline.get("run_id"):
        checks.append(_fail("P1", "timeline_run_id", "timeline.run_id is missing"))
    else:
        checks.append(_pass("P1", "timeline_run_id", "timeline.run_id is present"))

    if not timeline.get("created_at"):
        checks.append(_fail("P1", "timeline_created_at", "timeline.created_at is missing"))
    else:
        checks.append(_pass("P1", "timeline_created_at", "timeline.created_at is present"))

    events = timeline.get("events")
    if not isinstance(events, list):
        checks.append(_fail("P1", "timeline_events_array", "timeline.events is not an array"))
        return 0, run_id, timeline
    checks.append(_pass("P1", "timeline_events_array", "timeline.events is an array"))

    if len(events) != 6:
        checks.append(_fail("P1", "timeline_events_count", "timeline.events length must be 6"))
    else:
        checks.append(_pass("P1", "timeline_events_count", "timeline has 6 events"))

    event_order = [event.get("event") if isinstance(event, dict) else None for event in events]
    if event_order != EXPECTED_EVENTS:
        checks.append(_fail("P1", "timeline_event_order", "timeline event order is invalid"))
    else:
        checks.append(_pass("P1", "timeline_event_order", "timeline event order is valid"))

    for index, event in enumerate(events):
        name = f"timeline_event_{index}_contract"
        if not isinstance(event, dict):
            checks.append(_fail("P1", name, f"events[{index}] is not an object"))
            continue
        missing = [
            field
            for field in ("event", "run_id", "timestamp")
            if field not in event or not event[field]
        ]
        if "data" not in event and "metadata" not in event:
            missing.append("data_or_metadata")
        if missing:
            checks.append(_fail("P1", name, f"events[{index}] is missing required field(s)"))
        else:
            checks.append(_pass("P1", name, f"events[{index}] has required fields"))

    eval_event = _find_event(events, "EVALUATION_RESULT")
    if eval_event is None:
        checks.append(_fail("P1", "quality_signals_present", "EVALUATION_RESULT is missing"))
        return len(events), run_id, timeline

    data = eval_event.get("data")
    quality_signals = data.get("quality_signals") if isinstance(data, dict) else None
    if not isinstance(quality_signals, dict):
        checks.append(
            _fail(
                "P1",
                "quality_signals_present",
                "EVALUATION_RESULT.data.quality_signals is missing",
            )
        )
        return len(events), run_id, timeline
    checks.append(_pass("P1", "quality_signals_present", "quality_signals is present"))

    missing_signals = [key for key in REQUIRED_QUALITY_SIGNALS if key not in quality_signals]
    non_boolean = [
        key
        for key in REQUIRED_QUALITY_SIGNALS
        if key in quality_signals and not isinstance(quality_signals[key], bool)
    ]
    if missing_signals:
        checks.append(
            _fail(
                "P1",
                "quality_signals_required_fields",
                "quality_signals is missing required field(s)",
            )
        )
    else:
        checks.append(
            _pass("P1", "quality_signals_required_fields", "quality_signals has required fields")
        )
    if non_boolean:
        checks.append(
            _fail("P1", "quality_signals_boolean", "quality_signals has non-boolean field(s)")
        )
    else:
        checks.append(_pass("P1", "quality_signals_boolean", "quality_signals are boolean"))

    return len(events), run_id, timeline


def _validate_clarify_result(
    bundle_dir: Path, checks: list[Check]
) -> tuple[str | None, Any | None]:
    result_path = bundle_dir / "clarify-validation-result.json"
    if not result_path.is_file():
        return None, None

    clarify_result, error = _read_json(result_path)
    if error is not None or not isinstance(clarify_result, dict):
        checks.append(
            _fail(
                "P1",
                "clarify_validation_valid_json",
                "clarify-validation-result.json is invalid JSON",
            )
        )
        return None, None
    checks.append(
        _pass("P1", "clarify_validation_valid_json", "clarify validation result JSON is valid")
    )

    if clarify_result.get("schema_version") != CLARIFY_RESULT_SCHEMA_VERSION:
        checks.append(
            _fail(
                "P1",
                "clarify_validation_schema_version",
                "clarify schema_version must be clarify.validation_result.v0",
            )
        )
    else:
        checks.append(
            _pass("P1", "clarify_validation_schema_version", "clarify schema_version is valid")
        )

    status = clarify_result.get("status")
    if status not in ("passed", "failed", "skipped"):
        checks.append(
            _fail(
                "P1",
                "clarify_validation_status",
                "clarify status must be passed, failed, or skipped",
            )
        )
    elif status == "failed":
        checks.append(_fail("P1", "clarify_validation_status", "clarify validation failed"))
    elif status == "skipped":
        checks.append(_warn("P1", "clarify_validation_status", "clarify validation was skipped"))
    else:
        checks.append(_pass("P1", "clarify_validation_status", "clarify validation passed"))

    commands = clarify_result.get("commands")
    if not isinstance(commands, list):
        checks.append(
            _fail(
                "P1",
                "clarify_validation_commands",
                "clarify commands is missing or not an array",
            )
        )
        return status if isinstance(status, str) else None, clarify_result
    checks.append(_pass("P1", "clarify_validation_commands", "clarify commands is an array"))

    if status == "passed":
        command_errors = []
        for index, command in enumerate(commands):
            if not isinstance(command, dict):
                command_errors.append(index)
                continue
            if any(
                field not in command
                for field in ("command", "exit_code", "status", "duration_ms")
            ):
                command_errors.append(index)
                continue
            if command.get("exit_code") != 0 or command.get("status") != "passed":
                command_errors.append(index)
        if command_errors:
            checks.append(
                _fail(
                    "P1",
                    "clarify_validation_passed_commands",
                    "passed clarify validation contains failing or malformed command(s)",
                )
            )
        else:
            checks.append(
                _pass(
                    "P1",
                    "clarify_validation_passed_commands",
                    "passed clarify validation commands passed",
                )
            )

    return status if isinstance(status, str) else None, clarify_result


def _run_boundary_checks(
    bundle_dir: Path,
    checks: list[Check],
    loaded_json: dict[str, Any],
) -> None:
    key_names: list[str] = []
    local_path_found = False

    for filename in JSON_FILES_TO_SCAN:
        path = bundle_dir / filename
        if filename in loaded_json:
            data = loaded_json[filename]
        elif path.is_file():
            data, error = _read_json(path)
            if error is not None:
                continue
        else:
            continue
        key_names.extend(_iter_keys(data))
        local_path_found = local_path_found or _json_contains_local_path(data)

    lower_keys = [key.lower() for key in key_names]
    if any(key in FORBIDDEN_KEYS for key in lower_keys):
        checks.append(
            _fail("P1", "evidence_only_forbidden_keys", "forbidden runtime or policy key found")
        )
    else:
        checks.append(
            _pass("P1", "evidence_only_forbidden_keys", "no forbidden runtime or policy keys found")
        )

    if any(any(secret in key for secret in SECRET_LIKE_KEYS) for key in lower_keys):
        checks.append(_warn("P2", "secret_like_keys", "suspicious secret-like key found"))
    else:
        checks.append(_pass("P2", "secret_like_keys", "no suspicious secret-like keys found"))

    if local_path_found:
        checks.append(_warn("P2", "local_path_references", "local machine path reference found"))
    else:
        checks.append(
            _pass("P2", "local_path_references", "no local machine path references found")
        )


def validate_bundle(bundle_dir: Path) -> dict[str, Any]:
    checks: list[Check] = []

    if not bundle_dir.is_dir():
        checks.append(_fail("P0", "bundle_dir_exists", "bundle directory does not exist"))
        return _build_result(checks, run_id=None, timeline_events=0, clarify_status=None)

    checks.append(_pass("P0", "bundle_dir_exists", "bundle directory exists"))

    manifest, manifest_run_id = _validate_manifest(bundle_dir, checks)
    timeline_events, timeline_run_id, timeline = _validate_timeline(bundle_dir, checks)
    clarify_status, clarify_result = _validate_clarify_result(bundle_dir, checks)

    loaded_json = {
        key: value
        for key, value in (
            ("manifest.json", manifest),
            ("ailuros.timeline.v0.json", timeline),
            ("clarify-validation-result.json", clarify_result),
        )
        if value is not None
    }
    _run_boundary_checks(bundle_dir, checks, loaded_json)

    run_id = manifest_run_id or timeline_run_id
    return _build_result(
        checks,
        run_id=run_id,
        timeline_events=timeline_events,
        clarify_status=clarify_status,
    )


def _build_result(
    checks: list[Check],
    run_id: str | None,
    timeline_events: int,
    clarify_status: str | None,
) -> dict[str, Any]:
    status = _status_from_checks(checks)
    blocking = sum(1 for check in checks if check.status == "FAIL")
    warnings = sum(1 for check in checks if check.status == "WARN")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "source": "clarify",
        "status": status,
        "run_id": run_id,
        "checks": [check.to_dict() for check in checks],
        "summary": {
            "timeline_events": timeline_events,
            "clarify_validation_status": clarify_status,
            "blocking_issues": blocking,
            "warnings": warnings,
        },
    }


def _escape_markdown_table(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render_report(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Ailuros Clarify Evidence Validation Report",
        "",
        "## Status",
        "",
        result["status"],
        "",
        "## Summary",
        "",
        "- Source: clarify",
        f"- Run ID: {result.get('run_id') or 'unknown'}",
        f"- Timeline events: {summary['timeline_events']}",
        f"- Clarify validation: {summary.get('clarify_validation_status') or 'unknown'}",
        f"- Blocking issues: {summary['blocking_issues']}",
        f"- Warnings: {summary['warnings']}",
        "",
        "## Checks",
        "",
        "| Level | Check | Status | Message |",
        "|---|---|---|---|",
    ]
    for check in result["checks"]:
        lines.append(
            "| {level} | {name} | {status} | {message} |".format(
                level=_escape_markdown_table(check["level"]),
                name=_escape_markdown_table(check["name"]),
                status=_escape_markdown_table(check["status"]),
                message=_escape_markdown_table(check["message"]),
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Offline validation only",
            "- No HTTP ingestion",
            "- No runtime policy execution",
            "- No blocking / approval / human-review action",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(bundle_dir: Path, result: dict[str, Any]) -> None:
    (bundle_dir / "ailuros-validation-result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "ailuros-validation-report.md").write_text(
        render_report(result),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process Clarify evidence data offline.")
    parser.add_argument("--bundle", required=True, help="Clarify evidence bundle directory")
    args = parser.parse_args(argv)

    bundle_dir = Path(args.bundle)
    result = validate_bundle(bundle_dir)

    if bundle_dir.is_dir():
        write_outputs(bundle_dir, result)

    print(f"Ailuros Clarify validation: {result['status']}")
    print(
        "Blocking issues: {blocking}, Warnings: {warnings}".format(
            blocking=result["summary"]["blocking_issues"],
            warnings=result["summary"]["warnings"],
        )
    )
    for check in result["checks"]:
        if check["status"] != "PASS":
            print(f"  [{check['status']}] {check['name']}: {check['message']}")

    return EXIT_FAIL if result["status"] == "FAIL" else EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
