from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ailuros.audit_package.models import AuditPackage, PackageValidationResult


def decide_audit_package(
    validation: PackageValidationResult,
    package: AuditPackage,
) -> PackageValidationResult:
    if not validation.valid:
        return validation
    decisions = list(_iter_dict_records(package.decisions))
    if any(_is_block_decision(decision) for decision in decisions):
        return PackageValidationResult(
            valid=True,
            decision="FAIL",
            reasons=["blocking governance decision present"],
        )
    if any(_is_review_decision(decision) for decision in decisions):
        return PackageValidationResult(
            valid=True,
            decision="REVIEW_REQUIRED",
            reasons=["review governance decision present"],
        )
    return validation


def _iter_dict_records(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item


def _decision_value(record: dict[str, Any]) -> str:
    for key in ("decision", "action", "status"):
        value = record.get(key)
        if isinstance(value, str):
            return value.lower().replace("-", "_")
    return ""


def _is_block_decision(record: dict[str, Any]) -> bool:
    return _decision_value(record) in {"block", "blocked", "blocking", "fail", "failed"}


def _is_review_decision(record: dict[str, Any]) -> bool:
    return _decision_value(record) in {"require_review", "review", "review_required"}
