"""Deterministic capability-level conformance for canonical evidence packages.

Given a canonical evidence package, this reports, for each Ailuros governance
capability, whether the package carries the minimum canonical evidence required
to evaluate that capability. It reads only canonical structured events
(``event_type`` and structured ``payload`` fields); producer, agent and
framework metadata never enters the decision logic.

This is evidence sufficiency reporting, not structural package validation and
not runtime governance. Structural package validity is reported separately
(``package_valid``) and is deliberately kept out of the capability statuses so
the two concerns never bleed into each other.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ailuros._compat import StrEnum
from ailuros.adapters.evidence_package.validator import (
    validate_evidence_package_contract,
)
from ailuros.evidence_normalization import normalize_external_evidence_event


class CapabilityStatus(StrEnum):
    """Closed status vocabulary for a capability's evidence sufficiency.

    ``unsupported`` means Ailuros has no canonical evaluation mechanism for the
    capability; it is never emitted for the standard capability matrix below,
    all of whose capabilities are supported.
    """

    EVALUABLE = "evaluable"
    MISSING_EVIDENCE = "missing_evidence"
    UNSUPPORTED = "unsupported"


class CapabilityConformance(BaseModel):
    """Capability-level conformance: status plus precise missing evidence ids."""

    model_config = ConfigDict(extra="forbid")

    capability: str
    status: CapabilityStatus
    missing_evidence: list[str] = Field(default_factory=list)


class EvidenceConformanceResult(BaseModel):
    """Package-level conformance report.

    ``package_valid`` is structural package validity (from the contract
    validator). It is kept separate from the per-capability evidence statuses by
    design: a structurally valid package can still be missing evidence, and a
    structurally invalid package does not get fabricated capability statuses.
    """

    model_config = ConfigDict(extra="forbid")

    package_valid: bool
    source: str | None = None
    schema_version: str | None = None
    run_id: str | None = None
    events_count: int | None = None
    capabilities: list[CapabilityConformance] = Field(default_factory=list)


@dataclass(frozen=True)
class _CapabilitySpec:
    """Declarative evidence requirement for one governance capability.

    ``alternatives`` is a tuple of evidence-id sets; the capability is
    ``evaluable`` when at least one set is fully present in the package's
    canonical events. ``evidence_ids`` is the ordered list of evidence ids
    reported as missing when the capability is not evaluable.

    An evidence id is either a canonical event type (``"run_started"``) or a
    structured payload reference (``"authority_evidence.payload.actor"``).
    """

    id: str
    alternatives: tuple[frozenset[str], ...]
    evidence_ids: tuple[str, ...]


# The minimum canonical evidence required to evaluate each capability. This is
# derived from the projection surface (src/ailuros/projection.py): a capability
# is evaluable only when the package carries the canonical structured events the
# projection reads to derive that capability's facts. No producer label or
# free-form text is consulted.
_CAPABILITY_SPECS: tuple[_CapabilitySpec, ...] = (
    _CapabilitySpec(
        id="lifecycle",
        alternatives=(
            frozenset({"run_started"}),
            frozenset({"run_completed"}),
            frozenset({"run_failed"}),
        ),
        evidence_ids=("run_started", "run_completed", "run_failed"),
    ),
    _CapabilitySpec(
        id="outcome",
        alternatives=(
            frozenset({"run_completed"}),
            frozenset({"run_failed"}),
        ),
        evidence_ids=("run_completed", "run_failed"),
    ),
    _CapabilitySpec(
        id="regression_prerequisites",
        alternatives=(
            frozenset({"run_completed"}),
            frozenset({"run_failed"}),
        ),
        evidence_ids=("run_completed", "run_failed"),
    ),
    _CapabilitySpec(
        id="authority",
        alternatives=(frozenset({"authority_evidence.payload.actor"}),),
        evidence_ids=("authority_evidence.payload.actor",),
    ),
    _CapabilitySpec(
        id="approval",
        alternatives=(frozenset({"approval_evidence.payload.subject"}),),
        evidence_ids=("approval_evidence.payload.subject",),
    ),
    _CapabilitySpec(
        id="budget",
        alternatives=(
            frozenset(
                {"budget_evidence.payload.subject", "budget_evidence.payload.unit"}
            ),
        ),
        evidence_ids=(
            "budget_evidence.payload.subject",
            "budget_evidence.payload.unit",
        ),
    ),
    _CapabilitySpec(
        id="scope",
        alternatives=(frozenset({"project_scope"}),),
        evidence_ids=("project_scope",),
    ),
    _CapabilitySpec(
        id="validation",
        alternatives=(frozenset({"project_validation"}),),
        evidence_ids=("project_validation",),
    ),
)

_SPEC_BY_ID: dict[str, _CapabilitySpec] = {
    spec.id: spec for spec in _CAPABILITY_SPECS
}


def capability_ids() -> tuple[str, ...]:
    """The deterministic ordered ids of the standard capability matrix."""
    return tuple(spec.id for spec in _CAPABILITY_SPECS)


def _events_from_timeline(package_dir: str | Path) -> list[dict[str, Any]]:
    """Best-effort read of canonical events from ``timeline.json``.

    Returns ``[]`` when the timeline is absent, unreadable, or does not contain
    a JSON array of objects. This keeps conformance computable (as
    missing-evidence) even for structurally invalid packages.
    """
    timeline_path = Path(package_dir) / "timeline.json"
    if not timeline_path.is_file():
        return []
    try:
        raw = json.loads(timeline_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, dict):
        return []
    events = raw.get("events")
    if not isinstance(events, list):
        return []
    raw_events = [event for event in events if isinstance(event, dict)]
    return [normalize_external_evidence_event(event) for event in raw_events]


def _evidence_present(events: list[dict[str, Any]], evidence_id: str) -> bool:
    """Whether any canonical event satisfies a structured evidence identifier."""
    if ".payload." in evidence_id:
        event_type, _, field = evidence_id.partition(".payload.")
        for event in events:
            if event.get("event_type") != event_type:
                continue
            payload = event.get("payload")
            if isinstance(payload, dict):
                value = payload.get(field)
                if isinstance(value, str) and value:
                    return True
        return False
    return any(event.get("event_type") == evidence_id for event in events)


def evaluate_capability(
    events: list[dict[str, Any]],
    capability_id: str,
) -> CapabilityConformance:
    """Evaluate one capability against canonical structured events."""
    spec = _SPEC_BY_ID.get(capability_id)
    if spec is None:
        return CapabilityConformance(
            capability=capability_id,
            status=CapabilityStatus.UNSUPPORTED,
        )

    satisfied = {
        evidence_id
        for evidence_id in spec.evidence_ids
        if _evidence_present(events, evidence_id)
    }
    if any(group <= satisfied for group in spec.alternatives):
        return CapabilityConformance(
            capability=spec.id,
            status=CapabilityStatus.EVALUABLE,
        )

    missing = [
        evidence_id
        for evidence_id in spec.evidence_ids
        if evidence_id not in satisfied
    ]
    return CapabilityConformance(
        capability=spec.id,
        status=CapabilityStatus.MISSING_EVIDENCE,
        missing_evidence=missing,
    )


def evaluate_evidence_conformance(
    package_dir: str | Path,
) -> EvidenceConformanceResult:
    """Evaluate capability-level evidence conformance for a package directory."""
    validation = validate_evidence_package_contract(package_dir)
    events = _events_from_timeline(package_dir)
    capabilities = [
        evaluate_capability(events, spec.id) for spec in _CAPABILITY_SPECS
    ]
    return EvidenceConformanceResult(
        package_valid=validation.ok,
        source=validation.source,
        schema_version=validation.schema_version,
        run_id=validation.run_id,
        events_count=validation.events_count,
        capabilities=capabilities,
    )


def conformance_result_to_dict(
    result: EvidenceConformanceResult,
) -> dict[str, Any]:
    """Convert a conformance result to stable JSON-compatible data."""
    return {
        "package_valid": result.package_valid,
        "source": result.source,
        "schema_version": result.schema_version,
        "run_id": result.run_id,
        "events_count": result.events_count,
        "capabilities": [
            {
                "capability": item.capability,
                "status": item.status.value,
                "missing_evidence": list(item.missing_evidence),
            }
            for item in result.capabilities
        ],
    }


def conformance_result_to_json(result: EvidenceConformanceResult) -> str:
    """Serialize a conformance result to deterministic JSON text.

    Keys are sorted so the output is stable across runs; list order (capability
    order) is fixed by the capability matrix.
    """
    return json.dumps(conformance_result_to_dict(result), indent=2, sort_keys=True)


def conformance_result_to_markdown(result: EvidenceConformanceResult) -> str:
    """Render a conformance result as deterministic Markdown."""
    lines = [
        "# Evidence Capability Conformance",
        "",
        f"Package valid: {result.package_valid}",
        f"Source: {result.source}",
        f"Schema version: {result.schema_version}",
        f"Run id: {result.run_id}",
        f"Events count: {result.events_count}",
        "",
        "| Capability | Status | Missing evidence |",
        "|---|---|---|",
    ]
    for item in result.capabilities:
        missing = ", ".join(item.missing_evidence) if item.missing_evidence else "-"
        lines.append(f"| {item.capability} | {item.status.value} | {missing} |")
    return "\n".join(lines)
