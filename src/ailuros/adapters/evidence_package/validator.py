from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ailuros.core.validation import ValidationResult
from ailuros.models.event import RuntimeEventType

# Canonical event-type vocabulary. Well-formed events whose type is outside this
# set are preserved as warnings rather than errors.
_KNOWN_EVENT_TYPES = {member.value for member in RuntimeEventType}

# Manifest fields that must be present and non-empty.
_REQUIRED_MANIFEST_FIELDS = (
    "package_version",
    "source",
    "governance_mode",
    "schema_version",
    "run_id",
    "generated_at",
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_files(
    manifest: dict[str, Any],
    package_dir: Path,
    errors: list[str],
) -> None:
    files = manifest.get("files")
    if not isinstance(files, list):
        errors.append("manifest 'files' must be an array")
        return
    if not files:
        errors.append("manifest 'files' array must not be empty")
        return

    for entry in files:
        if isinstance(entry, str):
            name, required = entry, True
        elif isinstance(entry, dict):
            name = entry.get("name")
            required = bool(entry.get("required", True))
        else:
            errors.append("manifest 'files' entries must be strings or objects")
            continue

        if not isinstance(name, str) or not name:
            errors.append("manifest 'files' entry missing 'name'")
            continue

        exists = (package_dir / name).is_file()
        if required and not exists:
            errors.append(f"required file missing: {name}")
        # Optional missing files are tolerated and do not fail validation.


def _validate_manifest(
    manifest: dict[str, Any],
    package_dir: Path,
    errors: list[str],
) -> None:
    for field in _REQUIRED_MANIFEST_FIELDS:
        value = manifest.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"manifest field missing or empty: {field}")

    if not _parse_timestamp(manifest.get("generated_at")):
        errors.append("manifest 'generated_at' is not a parseable timestamp")

    # 'target' is optional; validate type only when present.
    if "target" in manifest and not isinstance(manifest["target"], str):
        errors.append("manifest 'target' must be a string when present")

    _validate_files(manifest, package_dir, errors)


def _validate_timeline(
    timeline: Any,
    manifest: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> int:
    if not isinstance(timeline, dict):
        errors.append("timeline must be an object with 'events'")
        return 0

    schema_version = timeline.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version:
        errors.append("timeline field missing or empty: schema_version")
    elif schema_version != manifest.get("schema_version"):
        errors.append("timeline schema_version does not match manifest schema_version")

    run_id = timeline.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        errors.append("timeline field missing or empty: run_id")
    elif run_id != manifest.get("run_id"):
        errors.append("timeline run_id does not match manifest run_id")

    events = timeline.get("events")
    if not isinstance(events, list):
        errors.append("timeline 'events' must be an array")
        return 0
    if not events:
        errors.append("timeline 'events' must not be empty")
        return 0

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"event[{index}] must be an object")
            continue

        event_type = event.get("event_type")
        if not isinstance(event_type, str) or not event_type:
            errors.append(f"event[{index}] missing event_type")
        elif event_type not in _KNOWN_EVENT_TYPES:
            warnings.append(f"event[{index}] has unknown event_type: {event_type}")

        if not _parse_timestamp(event.get("timestamp")):
            errors.append(f"event[{index}] has invalid timestamp")

    return len(events)


def validate_evidence_package_contract(package_dir: str | Path) -> ValidationResult:
    """Validate the manifest + timeline contract of a canonical evidence package.

    Returns a generic :class:`ValidationResult`. This does not make any
    governance decision; it only reports structural validity.
    """
    pkg_path = Path(package_dir)
    errors: list[str] = []
    warnings: list[str] = []

    manifest_path = pkg_path / "manifest.json"
    timeline_path = pkg_path / "timeline.json"

    if not manifest_path.is_file():
        errors.append("required file missing: manifest.json")
    if not timeline_path.is_file():
        errors.append("required file missing: timeline.json")

    if errors:
        return ValidationResult(ok=False, errors=errors, warnings=warnings)

    try:
        manifest = _load_json(manifest_path)
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in manifest.json: {exc}")
        manifest = None
    try:
        timeline = _load_json(timeline_path)
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in timeline.json: {exc}")
        timeline = None

    if not isinstance(manifest, dict):
        if manifest is not None:
            errors.append("manifest.json must be a JSON object")
        return ValidationResult(ok=False, errors=errors, warnings=warnings)

    _validate_manifest(manifest, pkg_path, errors)
    events_count = _validate_timeline(timeline, manifest, errors, warnings)

    return ValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        source=manifest.get("source"),
        schema_version=manifest.get("schema_version"),
        run_id=manifest.get("run_id"),
        events_count=events_count,
    )
