from __future__ import annotations

import json
import sys
from pathlib import Path

EXIT_PASS = 0
EXIT_WARN = 0
EXIT_FAIL = 1

REQUIRED_SCHEMA_VERSION = "ailuros.evidence_bundle.v0"
REQUIRED_TIMELINE_SCHEMA_VERSION = "ailuros.timeline.v0"
REQUIRED_CLARIFY_SCHEMA_VERSION = "clarify.validation_result.v0"
REQUIRED_EVENT_ORDER = [
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
FORBIDDEN_KEYS = [
    "policy_decision",
    "approval_status",
    "human_review_required",
    "policy_action",
    "blocking_action",
    "runtime_blocked",
]
SUSPICIOUS_SECRET_KEYS = [
    "token",
    "password",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
]
LOCAL_PATH_PATTERNS = ["C:\\", "/Users/", ".everrun", "node_modules"]


class CheckResult:
    def __init__(self, name: str):
        self.name = name
        self.status = "PASS"
        self.message = ""

    def fail(self, message: str) -> None:
        self.status = "FAIL"
        self.message = message

    def warn(self, message: str) -> None:
        if self.status == "PASS":
            self.status = "WARN"
        self.message = message

    def to_dict(self) -> dict:
        return {"check": self.name, "status": self.status, "message": self.message}


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _case_insensitive_scan(obj, depth: int = 0) -> list[str]:
    keys: list[str] = []
    if depth > 20:
        return keys
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.append(k)
            keys.extend(_case_insensitive_scan(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            keys.extend(_case_insensitive_scan(item, depth + 1))
    return keys


def _keys_lower(keys: list[str]) -> list[str]:
    return [k.lower() for k in keys]


def validate_bundle(bundle_dir: Path) -> tuple[list[CheckResult], str]:
    checks: list[CheckResult] = []
    status = "PASS"

    def add(check: CheckResult) -> None:
        nonlocal status
        checks.append(check)
        if check.status == "FAIL":
            status = "FAIL"
        elif check.status == "WARN" and status != "FAIL":
            status = "WARN"

    check = CheckResult("bundle_dir_exists")
    if not bundle_dir.is_dir():
        check.fail(f"Bundle directory not found: {bundle_dir}")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("manifest_exists")
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        check.fail("manifest.json is missing")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("manifest_valid_json")
    manifest = _read_json(manifest_path)
    if manifest is None:
        check.fail("manifest.json is missing or invalid JSON")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("manifest_schema_version")
    if manifest.get("schema_version") != REQUIRED_SCHEMA_VERSION:
        check.fail(
            f"manifest.schema_version expected {REQUIRED_SCHEMA_VERSION!r}, "
            f"got {manifest.get('schema_version')!r}"
        )
        add(check)
        return checks, status
    add(check)

    check = CheckResult("manifest_producer")
    if manifest.get("producer") != "clarify":
        check.fail(
            f"manifest.producer expected 'clarify', got {manifest.get('producer')!r}"
        )
        add(check)
        return checks, status
    add(check)

    check = CheckResult("manifest_artifacts")
    artifacts = manifest.get("artifacts")
    if artifacts is None:
        check.fail("manifest.artifacts is missing")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("manifest_artifacts_exist")
    missing_artifacts = []
    for artifact in artifacts:
        if not (bundle_dir / artifact).is_file():
            missing_artifacts.append(artifact)
    if missing_artifacts:
        check.fail(f"Missing manifest artifacts: {missing_artifacts}")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("timeline_exists")
    timeline_path = bundle_dir / "ailuros.timeline.v0.json"
    if not timeline_path.is_file():
        check.fail("ailuros.timeline.v0.json is missing")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("clarify_validation_result_exists")
    clarify_result_path = bundle_dir / "clarify-validation-result.json"
    if not clarify_result_path.is_file():
        check.fail("clarify-validation-result.json is missing")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("timeline_valid_json")
    timeline = _read_json(timeline_path)
    if timeline is None:
        check.fail("Timeline JSON is invalid or not an object")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("timeline_schema_version")
    if timeline.get("schema_version") != REQUIRED_TIMELINE_SCHEMA_VERSION:
        check.fail(
            f"timeline.schema_version expected {REQUIRED_TIMELINE_SCHEMA_VERSION!r}, "
            f"got {timeline.get('schema_version')!r}"
        )
        add(check)
        return checks, status
    add(check)

    check = CheckResult("timeline_run_id")
    if not timeline.get("run_id"):
        check.fail("timeline.run_id is missing or empty")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("timeline_created_at")
    if not timeline.get("created_at"):
        check.fail("timeline.created_at is missing or empty")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("timeline_events_array")
    events = timeline.get("events")
    if not isinstance(events, list):
        check.fail("timeline.events is not an array")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("timeline_events_count")
    if len(events) != 6:
        check.fail(f"timeline.events length expected 6, got {len(events)}")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("timeline_event_order")
    actual_order = [e.get("event") if isinstance(e, dict) else None for e in events]
    expected_order = list(REQUIRED_EVENT_ORDER)
    if actual_order != expected_order:
        check.fail(
            f"timeline event order expected {expected_order}, got {actual_order}"
        )
        add(check)
        return checks, status
    add(check)

    for idx, event in enumerate(events):
        check = CheckResult(f"timeline_event_{idx}_structure")
        if not isinstance(event, dict):
            check.fail(f"events[{idx}] is not an object")
            add(check)
            continue
        if not event.get("event"):
            check.fail(f"events[{idx}].event is missing")
        if not event.get("run_id"):
            check.fail(f"events[{idx}].run_id is missing")
        if not event.get("timestamp"):
            check.fail(f"events[{idx}].timestamp is missing")
        has_data = "data" in event
        has_metadata = "metadata" in event
        if not has_data and not has_metadata:
            check.fail(f"events[{idx}] has neither data nor metadata")
        if check.message:
            add(check)

    check = CheckResult("evaluation_result_quality_signals")
    eval_event = None
    for event in events:
        if isinstance(event, dict) and event.get("event") == "EVALUATION_RESULT":
            eval_event = event
            break
    if eval_event is None:
        check.fail("EVALUATION_RESULT event not found")
        add(check)
        return checks, status

    quality_signals = None
    if isinstance(eval_event.get("data"), dict):
        quality_signals = eval_event["data"].get("quality_signals")
    if quality_signals is None:
        check.fail("EVALUATION_RESULT.data.quality_signals is missing")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("quality_signals_fields")
    missing_signals = [
        s for s in REQUIRED_QUALITY_SIGNALS if s not in quality_signals
    ]
    if missing_signals:
        check.fail(f"Missing quality signal(s): {missing_signals}")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("quality_signals_boolean")
    non_bool = []
    for sig in REQUIRED_QUALITY_SIGNALS:
        val = quality_signals.get(sig)
        if not isinstance(val, bool):
            non_bool.append(f"{sig}={val!r}")
    if non_bool:
        check.fail(f"Non-boolean quality signal(s): {non_bool}")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("clarify_validation_result_valid_json")
    clarify_data = _read_json(clarify_result_path)
    if clarify_data is None:
        check.fail("clarify-validation-result.json is invalid or not an object")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("clarify_schema_version")
    if clarify_data.get("schema_version") != REQUIRED_CLARIFY_SCHEMA_VERSION:
        check.fail(
            f"clarify-validation-result schema_version expected "
            f"{REQUIRED_CLARIFY_SCHEMA_VERSION!r}, "
            f"got {clarify_data.get('schema_version')!r}"
        )
        add(check)
        return checks, status
    add(check)

    check = CheckResult("clarify_status_valid")
    clarify_status = clarify_data.get("status")
    if clarify_status not in ("passed", "failed"):
        check.fail(
            f"clarify-validation-result status expected 'passed' or 'failed', "
            f"got {clarify_status!r}"
        )
        add(check)
        return checks, status
    add(check)

    check = CheckResult("clarify_status_passed")
    if clarify_status != "passed":
        check.fail(
            f"clarify-validation-result status is '{clarify_status}', expected 'passed'"
        )
        add(check)
        return checks, status
    add(check)

    check = CheckResult("clarify_commands_array")
    commands = clarify_data.get("commands")
    if commands is None or not isinstance(commands, list):
        check.fail("clarify-validation-result.commands is missing or not an array")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("clarify_command_structure")
    bad_commands = []
    for i, cmd in enumerate(commands):
        if not isinstance(cmd, dict):
            bad_commands.append(f"commands[{i}] is not an object")
            continue
        for field in ("command", "exit_code", "status", "duration_ms"):
            if field not in cmd:
                bad_commands.append(f"commands[{i}].{field} is missing")
    if bad_commands:
        check.fail("; ".join(bad_commands))
        add(check)
        return checks, status
    add(check)

    all_keys = []
    all_keys.extend(_case_insensitive_scan(manifest))
    all_keys.extend(_case_insensitive_scan(timeline))
    all_keys.extend(_case_insensitive_scan(clarify_data))
    all_keys_lower = _keys_lower(all_keys)

    check = CheckResult("forbidden_keys")
    forbidden_found = []
    for key_lower in all_keys_lower:
        if key_lower in [k.lower() for k in FORBIDDEN_KEYS]:
            forbidden_found.append(key_lower)
    if forbidden_found:
        check.fail(f"Forbidden runtime/policy key(s) found: {forbidden_found}")
        add(check)
        return checks, status
    add(check)

    check = CheckResult("suspicious_secret_keys")
    secret_found = set()
    for key_lower in all_keys_lower:
        if key_lower in [k.lower() for k in SUSPICIOUS_SECRET_KEYS]:
            secret_found.add(key_lower)
    if secret_found:
        check.warn(f"Suspicious secret-like key(s) found: {sorted(secret_found)}")
    add(check)

    check = CheckResult("local_path_references")
    all_text = json.dumps(manifest) + json.dumps(timeline) + json.dumps(clarify_data)
    path_found = []
    for pat in LOCAL_PATH_PATTERNS:
        if pat in all_text:
            path_found.append(pat)
    if path_found:
        check.warn(f"Local machine reference(s) found: {path_found}")
    add(check)

    check = CheckResult("runtime_integration_present")
    if "runtime_integration" not in manifest:
        check.warn("manifest.runtime_integration is absent")
    add(check)

    return checks, status


def write_results(
    bundle_dir: Path, checks: list[CheckResult], status: str
) -> None:
    blocking = sum(1 for c in checks if c.status == "FAIL")
    warnings = sum(1 for c in checks if c.status == "WARN")

    result = {
        "schema_version": "ailuros.validation_result.v0",
        "source": "clarify",
        "status": status,
        "checks": [c.to_dict() for c in checks],
        "summary": {
            "total": len(checks),
            "passed": sum(1 for c in checks if c.status == "PASS"),
            "warnings": warnings,
            "blocking_issues": blocking,
        },
    }

    result_path = bundle_dir / "ailuros-validation-result.json"
    result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    md_lines = [
        "# Clarify Evidence Bundle Validation Report",
        "",
        f"**Status:** {status}",
        "**Source:** clarify",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total Checks | {len(checks)} |",
        f"| Passed | {result['summary']['passed']} |",
        f"| Warnings | {warnings} |",
        f"| Blocking Issues | {blocking} |",
        "",
        "## Checks",
        "",
        "| # | Check | Status | Message |",
        "|---|---|---|---|",
    ]
    for i, c in enumerate(checks, 1):
        md_lines.append(f"| {i} | {c.name} | {c.status} | {c.message} |")

    report_path = bundle_dir / "ailuros-validation-report.md"
    report_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--bundle":
        print(
            "Usage: python scripts/validate_clarify_evidence_bundle.py "
            "--bundle <bundle-dir>",
            file=sys.stderr,
        )
        return EXIT_FAIL

    bundle_dir = Path(sys.argv[2]).resolve()
    checks, status = validate_bundle(bundle_dir)

    write_results(bundle_dir, checks, status)

    print(f"Status: {status}")
    blocking = sum(1 for c in checks if c.status == "FAIL")
    warnings = sum(1 for c in checks if c.status == "WARN")
    print(f"Blocking issues: {blocking}, Warnings: {warnings}")

    for c in checks:
        if c.status != "PASS":
            print(f"  [{c.status}] {c.name}: {c.message}")

    if status == "FAIL":
        return EXIT_FAIL
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
