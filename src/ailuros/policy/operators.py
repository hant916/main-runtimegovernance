from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from numbers import Real
from typing import Any

from ailuros.models import PolicyOperator
from ailuros.utils import MISSING


@dataclass(frozen=True)
class OperatorResult:
    matched: bool
    reason: str = ""


def evaluate_operator(
    operator: PolicyOperator, actual: Any, expected: Any = None
) -> OperatorResult:
    if operator is PolicyOperator.EXISTS:
        return OperatorResult(actual is not MISSING)
    if operator is PolicyOperator.NOT_EXISTS:
        return OperatorResult(actual is MISSING)
    if actual is MISSING:
        return OperatorResult(False, "missing field")
    if operator is PolicyOperator.EQ:
        return OperatorResult(actual == expected)
    if operator is PolicyOperator.NEQ:
        return OperatorResult(actual != expected)
    if operator in {PolicyOperator.GT, PolicyOperator.GTE, PolicyOperator.LT, PolicyOperator.LTE}:
        if not isinstance(actual, Real) or not isinstance(expected, Real):
            return OperatorResult(False, "numeric comparison requires numbers")
        if operator is PolicyOperator.GT:
            return OperatorResult(actual > expected)
        if operator is PolicyOperator.GTE:
            return OperatorResult(actual >= expected)
        if operator is PolicyOperator.LT:
            return OperatorResult(actual < expected)
        return OperatorResult(actual <= expected)
    if operator is PolicyOperator.IN:
        if not _iterable(expected):
            return OperatorResult(False, "expected iterable")
        return OperatorResult(actual in expected)
    if operator is PolicyOperator.NOT_IN:
        if not _iterable(expected):
            return OperatorResult(False, "expected iterable")
        return OperatorResult(actual not in expected)
    if operator is PolicyOperator.CONTAINS:
        try:
            return OperatorResult(expected in actual)
        except TypeError:
            return OperatorResult(False, "actual value is not searchable")
    if operator is PolicyOperator.REGEX:
        if not isinstance(actual, str) or not isinstance(expected, str):
            return OperatorResult(False, "regex requires strings")
        try:
            return OperatorResult(re.search(expected, actual) is not None)
        except re.error as exc:
            return OperatorResult(False, f"invalid regex: {exc}")
    return OperatorResult(False, f"unsupported operator: {operator}")


def _iterable(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, str)
