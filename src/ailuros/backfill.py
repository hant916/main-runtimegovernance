from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ailuros.adapters.evidence_package import (
    ImportStatus,
    ingest_evidence_package,
    load_evidence_package,
)
from ailuros.storage.sqlite_storage import SQLiteStorage


class BatchSummary(BaseModel):
    total: int = 0
    created: int = 0
    already_present: int = 0
    invalid: int = 0
    conflict: int = 0
    projected: int = 0
    projection_failed: int = 0
    failures: list[dict[str, Any]] = []
    coverage: dict[str, Any] = {}


def _is_package_dir(path: Path) -> bool:
    return (path / "manifest.json").is_file() and (path / "timeline.json").is_file()


def _read_package_coverage(pkg_dir: Path) -> dict[str, Any] | None:
    manifest_path = pkg_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(manifest, dict):
        return None
    pkg_metadata = manifest.get("pkg_metadata")
    if not isinstance(pkg_metadata, dict):
        return None
    cov = pkg_metadata.get("coverage")
    if not isinstance(cov, dict):
        return None
    return cov


def _merge_coverage(acc: dict[str, Any], cov: dict[str, Any] | None) -> dict[str, Any]:
    if cov is None:
        return acc
    for key, value in cov.items():
        if key not in acc:
            acc[key] = value
        elif isinstance(value, dict) and isinstance(acc[key], dict):
            for subkey, subvalue in value.items():
                if isinstance(subvalue, (int, float)) and isinstance(
                    acc[key].get(subkey), (int, float)
                ):
                    acc[key][subkey] = acc[key][subkey] + subvalue
                else:
                    acc[key][subkey] = subvalue
        elif isinstance(value, (int, float)) and isinstance(acc[key], (int, float)):
            acc[key] = acc[key] + value
    return acc


def discover_packages(root_dir: str | Path) -> list[Path]:
    root = Path(root_dir)
    if not root.is_dir():
        return []

    packages: list[Path] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and _is_package_dir(child):
            packages.append(child)
    return packages


def batch_import_project(
    storage: SQLiteStorage,
    root_dir: str | Path,
) -> BatchSummary:
    packages = discover_packages(root_dir)

    summary = BatchSummary(total=len(packages))
    if not packages:
        return summary

    for pkg_dir in packages:
        try:
            package = load_evidence_package(pkg_dir)
        except Exception as exc:
            summary.invalid += 1
            summary.failures.append(
                {"package_dir": str(pkg_dir), "stage": "load", "error": str(exc)}
            )
            continue

        try:
            result = ingest_evidence_package(storage, package)
        except Exception as exc:
            summary.invalid += 1
            summary.failures.append(
                {
                    "package_dir": str(pkg_dir),
                    "run_id": package.run_id,
                    "stage": "import",
                    "error": str(exc),
                }
            )
            continue

        if result.status == ImportStatus.CREATED:
            summary.created += 1
        elif result.status == ImportStatus.ALREADY_PRESENT:
            summary.already_present += 1
        elif result.status == ImportStatus.CONFLICT:
            summary.conflict += 1
            continue

        _merge_coverage(summary.coverage, _read_package_coverage(pkg_dir))

        try:
            from ailuros.projection import rebuild_projections_and_signals

            rebuild_projections_and_signals(storage, package.run_id)
            summary.projected += 1
        except Exception as exc:
            summary.projection_failed += 1
            summary.failures.append(
                {
                    "package_dir": str(pkg_dir),
                    "run_id": package.run_id,
                    "stage": "projection",
                    "error": str(exc),
                }
            )

    return summary
