from __future__ import annotations

from typing import Any

from ailuros.audit_package.models import AuditPackage, PackageValidationResult


def validate_audit_package(package: AuditPackage) -> PackageValidationResult:
    reasons: list[str] = []
    run_ids = _collect_run_ids(package)
    if len(set(run_ids)) > 1:
        reasons.append("mismatched run_id values: " + ", ".join(sorted(set(run_ids))))
    if reasons:
        return PackageValidationResult(valid=False, decision="FAIL", reasons=reasons)
    return PackageValidationResult(valid=True, decision="PASS", reasons=[])


def _collect_run_ids(package: AuditPackage) -> list[str]:
    records: list[tuple[str, Any]] = [
        ("manifest", package.manifest),
        ("run", package.run),
        ("timeline", package.timeline),
        ("decisions", package.decisions),
        ("evaluations", package.evaluations),
        ("regressions", package.regressions),
    ]
    values: list[str] = []
    for _, record in records:
        values.extend(_find_run_ids(record))
    return values


def _find_run_ids(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        run_id = value.get("run_id")
        if isinstance(run_id, str) and run_id:
            found.append(run_id)
        for nested in value.values():
            found.extend(_find_run_ids(nested))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_run_ids(item))
    return found
