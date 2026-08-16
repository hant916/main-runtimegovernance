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
    values: list[str] = []
    top_level_run_id = _top_level_run_id(package.manifest)
    if top_level_run_id is not None:
        values.append(top_level_run_id)
    top_level_run_id = _top_level_run_id(package.run)
    if top_level_run_id is not None:
        values.append(top_level_run_id)
    for records in (
        package.timeline,
        package.decisions,
        package.evaluations,
        package.regressions,
    ):
        values.extend(_record_list_run_ids(records))
    return values


def _top_level_run_id(value: Any) -> str | None:
    if isinstance(value, dict):
        run_id = value.get("run_id")
        if isinstance(run_id, str) and run_id:
            return run_id
    return None


def _record_list_run_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    run_ids: list[str] = []
    for item in value:
        run_id = _top_level_run_id(item)
        if run_id is not None:
            run_ids.append(run_id)
    return run_ids
