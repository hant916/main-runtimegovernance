from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ailuros.audit_package.models import (
    _AUDIT_PACKAGE_FILES,
    AuditPackage,
    AuditPackageLoadError,
)


def load_audit_package(path: Path) -> AuditPackage:
    package_dir = path.resolve()
    reasons: list[str] = []
    if not package_dir.is_dir():
        raise AuditPackageLoadError([f"audit package directory not found: {path}"])

    for file_name in _AUDIT_PACKAGE_FILES:
        if not (package_dir / file_name).is_file():
            reasons.append(f"missing required file: {file_name}")
    if reasons:
        raise AuditPackageLoadError(reasons)

    try:
        manifest = _read_json_file(package_dir / "manifest.json")
        run = _read_json_file(package_dir / "run.json")
        timeline = _read_jsonl_file(package_dir / "timeline.jsonl")
        decisions = _read_json_file(package_dir / "decisions.json")
        evaluations = _read_json_file(package_dir / "evaluations.json")
        regressions = _read_json_file(package_dir / "regressions.json")
    except AuditPackageLoadError:
        raise

    return AuditPackage(
        path=package_dir,
        manifest=manifest,
        run=run,
        timeline=timeline,
        decisions=decisions,
        evaluations=evaluations,
        regressions=regressions,
        summary=_read_text_file(package_dir / "summary.md"),
    )


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise AuditPackageLoadError(
            [f"malformed text in {path.name}: invalid UTF-8"]
        ) from exc
    except OSError as exc:
        raise AuditPackageLoadError(
            [f"failed to read {path.name}: {exc.strerror or exc}"]
        ) from exc


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuditPackageLoadError(
            [f"malformed JSON in {path.name}: line {exc.lineno} column {exc.colno}"]
        ) from exc


def _read_jsonl_file(path: Path) -> list[Any]:
    records: list[Any] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise AuditPackageLoadError(
                [f"malformed JSONL in {path.name}: line {line_number} column {exc.colno}"]
            ) from exc
    return records
