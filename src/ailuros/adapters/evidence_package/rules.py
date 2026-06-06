from __future__ import annotations

from collections.abc import Callable

from ailuros.core.audit import AuditDecision
from ailuros.core.validation import ValidationResult

# Severity ranking used to combine independent rule outcomes. The audit decision
# is the most severe outcome any rule produced.
_SEVERITY = {
    AuditDecision.PASS: 0,
    AuditDecision.WARN: 1,
    AuditDecision.FAIL: 2,
}


def _errors_fail(validation: ValidationResult) -> AuditDecision:
    """Any contract validation error fails the audit."""
    return AuditDecision.FAIL if validation.errors else AuditDecision.PASS


def _warnings_warn(validation: ValidationResult) -> AuditDecision:
    """Any contract validation warning warns the audit (without errors -> warn)."""
    return AuditDecision.WARN if validation.warnings else AuditDecision.PASS


# Minimal, source-neutral post-run rule set. Rules only read the generic
# ValidationResult; they do not encode any producer-specific risk semantics.
RULES: tuple[Callable[[ValidationResult], AuditDecision], ...] = (
    _errors_fail,
    _warnings_warn,
)


def evaluate_rules(validation: ValidationResult) -> tuple[AuditDecision, int]:
    """Evaluate the post-run rule set against a contract validation result.

    Returns the combined :class:`AuditDecision` (most severe rule outcome) and
    the number of rules evaluated. A clean validated package yields ``pass``;
    warnings without errors yield ``warn``; any error yields ``fail``.
    """
    decision = AuditDecision.PASS
    for rule in RULES:
        outcome = rule(validation)
        if _SEVERITY[outcome] > _SEVERITY[decision]:
            decision = outcome
    return decision, len(RULES)
