from __future__ import annotations

import json
from typing import Any

from ailuros.core.audit import AuditResult


def audit_result_to_dict(result: AuditResult) -> dict[str, Any]:
    """Convert an :class:`AuditResult` to stable JSON-compatible data.

    Warning and error order is preserved as produced by validation, which is
    deterministic for a given package.
    """
    return {
        "ok": result.ok,
        "decision": result.decision.value,
        "governance_mode": result.governance_mode,
        "source": result.source,
        "schema_version": result.schema_version,
        "run_id": result.run_id,
        "events_count": result.events_count,
        "rules_evaluated": result.rules_evaluated,
        "warnings": list(result.warnings),
        "errors": list(result.errors),
    }


def audit_result_to_json(result: AuditResult) -> str:
    """Serialize an :class:`AuditResult` to deterministic JSON text.

    Keys are sorted so the output is stable across runs; list order is preserved.
    """
    return json.dumps(audit_result_to_dict(result), indent=2, sort_keys=True)
