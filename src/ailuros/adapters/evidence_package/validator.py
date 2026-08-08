from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ailuros.core.validation import ValidationResult
from ailuros.models.event import RuntimeEventType

_V1_SCHEMA = "ailuros.timeline.v1"

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


def _check_path_traversal(value: str) -> bool:
    if not value:
        return False
    if value.startswith("/") or value.startswith("\\"):
        return True
    if len(value) >= 2 and value[0].isalpha() and value[1] == ":":
        return True
    parts = value.replace("\\", "/").split("/")
    if ".." in parts:
        return True
    return False


def _validate_v1_identity_and_uniqueness(
    timeline: dict[str, Any],
    errors: list[str],
) -> None:
    events = timeline.get("events")
    if not isinstance(events, list):
        return
    seen_ids: set[str] = set()
    for _i, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            continue
        if event_id in seen_ids:
            errors.append(f"duplicate event_id in timeline: {event_id}")
        seen_ids.add(event_id)


def _validate_v1_provenance_safety(
    manifest: dict[str, Any],
    errors: list[str],
) -> None:
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        return

    source_artifact = provenance.get("source_artifact")
    if isinstance(source_artifact, str) and _check_path_traversal(source_artifact):
        errors.append(
            "provenance.source_artifact must be a package-relative logical ref, "
            f"not a filesystem path: {source_artifact}"
        )

    source_pointer = provenance.get("source_pointer")
    if isinstance(source_pointer, str) and _check_path_traversal(source_pointer):
        errors.append(
            "provenance.source_pointer must be a package-relative logical ref, "
            f"not a filesystem path: {source_pointer}"
        )


def _validate_v1_counts(
    manifest: dict[str, Any],
    events_count: int,
    errors: list[str],
) -> None:
    pkg_metadata = manifest.get("pkg_metadata")
    if not isinstance(pkg_metadata, dict):
        return
    coverage = pkg_metadata.get("coverage")
    if not isinstance(coverage, dict):
        return

    declared_events = coverage.get("events")
    if isinstance(declared_events, int) and declared_events != events_count:
        errors.append(
            f"pkg_metadata.coverage.events declares {declared_events} events "
            f"but timeline contains {events_count}"
        )

    declared_files = coverage.get("files")
    if isinstance(declared_files, int):
        files_list = manifest.get("files", [])
        actual_files = len(files_list) if isinstance(files_list, list) else 0
        if declared_files != actual_files:
            errors.append(
                f"pkg_metadata.coverage.files declares {declared_files} files "
                f"but manifest declares {actual_files}"
            )


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
        name: str | None
        if isinstance(entry, str):
            name, required = entry, True
        elif isinstance(entry, dict):
            raw_name = entry.get("name")
            name = raw_name if isinstance(raw_name, str) else None
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

    if manifest.get("schema_version") == _V1_SCHEMA and isinstance(timeline, dict):
        _validate_v1_identity_and_uniqueness(timeline, errors)
        _validate_v1_provenance_safety(manifest, errors)
        _validate_v1_counts(manifest, events_count, errors)

    return ValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        source=manifest.get("source"),
        schema_version=manifest.get("schema_version"),
        run_id=manifest.get("run_id"),
        events_count=events_count,
    )
