from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ailuros.core.validation import ValidationResult
from ailuros.models.event import RuntimeEventType

_V1_SCHEMA = "ailuros.timeline.v1"
_DIGEST_HEX_LENGTHS = {"sha256": 64, "sha512": 128, "sha1": 40, "md5": 32}
_HEX_CHARS = frozenset("0123456789abcdef")

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
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.tzinfo.utcoffset(parsed) is not None


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


def _validate_v1_source_digest(
    manifest: dict[str, Any],
    warnings: list[str],
) -> None:
    """Check that a declared `pkg_metadata.source_digest` is well-formed.

    `source_digest` is a producer attestation about the *upstream source
    material* the exporter read (agent history, a run directory, an API
    response). Ailuros never receives that material, so the digest is
    structurally unverifiable here and is deliberately NOT treated as an
    integrity proof of the package files. What is checkable is its shape: a
    value that looks like a digest but is not one is misleading in an audit
    record, so a malformed value is surfaced as a warning.

    Well-formed = `<algo>:<lowercase-hex>` with a hex length matching the
    named algorithm. Absent (`None`) stays valid and unremarked.
    """
    pkg_metadata = manifest.get("pkg_metadata")
    if not isinstance(pkg_metadata, dict):
        return
    digest = pkg_metadata.get("source_digest")
    if digest is None:
        return
    if not isinstance(digest, str) or not digest.strip():
        warnings.append(
            "pkg_metadata.source_digest must be a non-empty string when present"
        )
        return
    if ":" not in digest:
        warnings.append(
            f"pkg_metadata.source_digest is not in '<algo>:<hex>' form: {digest!r} "
            "(unverified producer attestation)"
        )
        return
    algo, _, hexpart = digest.partition(":")
    expected = _DIGEST_HEX_LENGTHS.get(algo.lower())
    if expected is None:
        warnings.append(
            f"pkg_metadata.source_digest uses unknown digest algorithm {algo!r} "
            "(unverified producer attestation)"
        )
        return
    if len(hexpart) != expected or not all(c in _HEX_CHARS for c in hexpart):
        warnings.append(
            f"pkg_metadata.source_digest declares {algo} but the value is not a "
            f"{expected}-character lowercase hex digest: {digest!r} "
            "(unverified producer attestation)"
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
        if not isinstance(value, str) or not value.strip():
            errors.append(f"manifest field missing or empty: {field}")

    if not _parse_timestamp(manifest.get("generated_at")):
        errors.append(
            "manifest 'generated_at' must be a complete timezone-aware "
            "ISO-8601 timestamp"
        )

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

    seen_ids: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"event[{index}] must be an object")
            continue

        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            errors.append(f"event[{index}] missing event_id")
            event_ref = f"event[{index}]"
        else:
            event_ref = f"event[{index}] (event_id '{event_id}')"
            if event_id in seen_ids:
                errors.append(
                    f"{event_ref} duplicates event_id in timeline: "
                    f"duplicate event_id '{event_id}'"
                )
            seen_ids.add(event_id)

        event_type = event.get("event_type")
        if not isinstance(event_type, str) or not event_type.strip():
            errors.append(f"{event_ref} missing event_type")
        elif event_type not in _KNOWN_EVENT_TYPES:
            warnings.append(f"{event_ref} has unknown event_type: {event_type}")

        if not _parse_timestamp(event.get("timestamp")):
            errors.append(
                f"{event_ref} has invalid timestamp; expected a complete "
                "timezone-aware ISO-8601 value"
            )

        if not isinstance(event.get("payload"), dict):
            errors.append(f"{event_ref} payload must be an object")

        scope_ref = event.get("scope_ref")
        if scope_ref is not None and not isinstance(scope_ref, str):
            errors.append(f"{event_ref} scope_ref must be a string when present")

    return len(events)


def validate_evidence_package_contract(
    package_dir: str | Path,
    *,
    strict: bool = True,
) -> ValidationResult:
    """Validate the manifest + timeline contract of a canonical evidence package.

    Returns a generic :class:`ValidationResult`. This does not make any
    governance decision; it only reports structural validity.

    ``strict`` controls whether declared pkg_metadata.coverage counts are
    cross-checked against actual content. Importers keep this ``False`` so a
    batch can aggregate declared coverage even when a manifest's numbers are
    ahead of (or behind) the shipped timeline; contract audits keep it ``True``.
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
        _validate_v1_provenance_safety(manifest, errors)
        _validate_v1_source_digest(manifest, warnings)
        if strict:
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
