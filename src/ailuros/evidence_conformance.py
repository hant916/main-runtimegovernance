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
from ailuros.evidence_normalization import normalize_external_evidence_event
from ailuros.projection import (
    _APPROVED_DECISIONS,
    _AUTHORITY_AUTHORIZED_STATUSES,
    _AUTHORITY_VIOLATION_STATUSES,
    _DENIED_DECISIONS,
)


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


class EvidenceInconsistency(BaseModel):
    """One deterministic contradiction between already-ingested structured claims.

    ``rule_id`` names the deterministic comparison rule that found the conflict.
    ``subject`` is the shared governance fact both claims address.
    ``values`` are the distinct, normalized claim values that disagree.
    ``evidence_ids`` are the exact event ids of the compared evidence items.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    subject: str
    values: list[str]
    evidence_ids: list[str]


class EvidenceConformanceResult(BaseModel):
    """Package-level conformance report.

    ``package_valid`` is structural package validity (from the contract
    validator). It is kept separate from the per-capability evidence statuses by
    design: a structurally valid package can still be missing evidence, and a
    structurally invalid package does not get fabricated capability statuses.

    ``inconsistencies`` is the deterministic evidence-consistency finding set:
    only incompatible structured claims about the same governance fact appear
    here. Missing evidence stays missing and unsupported evidence stays
    unsupported; neither is promoted into a contradiction.
    """

    model_config = ConfigDict(extra="forbid")

    package_valid: bool
    source: str | None = None
    schema_version: str | None = None
    run_id: str | None = None
    events_count: int | None = None
    capabilities: list[CapabilityConformance] = Field(default_factory=list)
    inconsistencies: list[EvidenceInconsistency] = Field(default_factory=list)


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


# ── Evidence consistency: deterministic contradictions over structured claims ─
#
# The consistency path compares only already-normalized structured claims about
# the same governance fact. It never parses free-form text, stderr, or guessed
# paths, and it never treats a missing or unsupported side as a contradiction.

_RULE_LIFECYCLE = "lifecycle_terminal_conflict"
_RULE_APPROVAL = "approval_decision_conflict"
_RULE_AUTHORITY = "authority_state_conflict"


def _normalize_token(value: Any) -> str | None:
    """Normalize a structured claim value to a comparable token.

    Only canonical structured values participate: non-empty strings and finite
    numbers. Booleans are excluded because a bare boolean is not a governance
    claim; everything else is treated as absent.
    """
    if isinstance(value, str):
        token = value.strip()
        return token.lower() if token else None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return repr(value)
    return None


def _lifecycle_token(event_type: str) -> str | None:
    """A terminal lifecycle event is a claim that the run ended.

    ``run_completed`` means the run ended successfully; ``run_failed`` means it
    ended in failure. ``run_started`` and everything else carry no terminal
    claim and therefore never enter the comparison.
    """
    if event_type == "run_completed":
        return "completed"
    if event_type == "run_failed":
        return "failed"
    return None


def _inconsistencies_for(
    events: list[dict[str, Any]],
) -> list[EvidenceInconsistency]:
    """Compute the deterministic, evidence-grounded inconsistency findings.

    Returns findings in a stable order (first conflicting event order). Every
    finding carries the deterministic rule id, the distinct claim values, and
    the exact event ids that were compared.
    """
    findings: list[EvidenceInconsistency] = []

    # lifecycle: run_completed and run_failed both claim a terminal state for
    # the same run; two different terminal states cannot both be true.
    lifecycle: dict[str, list[str]] = {}
    for event in events:
        event_type = event.get("event_type")
        token = _lifecycle_token(event_type)  # type: ignore[arg-type]
        if token is None:
            continue
        event_id = event.get("event_id")
        if isinstance(event_id, str) and event_id:
            lifecycle.setdefault(token, []).append(event_id)
    if "completed" in lifecycle and "failed" in lifecycle:
        findings.append(
            EvidenceInconsistency(
                rule_id=_RULE_LIFECYCLE,
                subject="run_terminal_state",
                values=["completed", "failed"],
                evidence_ids=sorted(
                    lifecycle["completed"] + lifecycle["failed"]
                ),
            )
        )

    # approval: two approval_evidence events about the same (subject, action)
    # that disagree on approved vs denied are incompatible.
    approval: dict[tuple[str, str], dict[str, list[str]]] = {}
    for event in events:
        if event.get("event_type") != "approval_evidence":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        subject = _normalize_token(payload.get("subject"))
        action = _normalize_token(payload.get("action"))
        decision = _normalize_token(payload.get("decision"))
        if subject is None or decision is None:
            continue
        approved = decision in _APPROVED_DECISIONS
        denied = decision in _DENIED_DECISIONS
        if not approved and not denied:
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            continue
        key = (subject, action if action is not None else "")
        slot = approval.setdefault(key, {})
        state = "approved" if approved else "denied"
        slot.setdefault(state, []).append(event_id)

    for (subject, action), states in approval.items():
        if "approved" not in states or "denied" not in states:
            continue
        subject_label = subject if not action else f"{subject}/{action}"
        findings.append(
            EvidenceInconsistency(
                rule_id=_RULE_APPROVAL,
                subject=subject_label,
                values=["approved", "denied"],
                evidence_ids=sorted(states["approved"] + states["denied"]),
            )
        )

    # authority: two authority_evidence events about the same (actor, action)
    # that disagree on authorized vs violation are incompatible.
    authority: dict[tuple[str, str], dict[str, list[str]]] = {}
    for event in events:
        if event.get("event_type") != "authority_evidence":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        actor = _normalize_token(payload.get("actor"))
        action = _normalize_token(payload.get("action"))
        status = _normalize_token(payload.get("status"))
        if actor is None or status is None:
            continue
        authorized = status in _AUTHORITY_AUTHORIZED_STATUSES
        violation = status in _AUTHORITY_VIOLATION_STATUSES
        if not authorized and not violation:
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            continue
        key = (actor, action if action is not None else "")
        slot = authority.setdefault(key, {})
        state = "authorized" if authorized else "violation"
        slot.setdefault(state, []).append(event_id)

    for (actor, action), states in authority.items():
        if "authorized" not in states or "violation" not in states:
            continue
        subject_label = actor if not action else f"{actor}/{action}"
        findings.append(
            EvidenceInconsistency(
                rule_id=_RULE_AUTHORITY,
                subject=subject_label,
                values=["authorized", "violation"],
                evidence_ids=sorted(states["authorized"] + states["violation"]),
            )
        )

    return findings


def detect_evidence_inconsistencies(
    events: list[dict[str, Any]],
) -> list[EvidenceInconsistency]:
    """Detect deterministic contradictions between already-structured claims.

    This is the public consistency boundary used by post-run evidence judgment.
    Inputs are canonical normalized events (see
    :func:`ailuros.evidence_normalization.normalize_external_evidence_event`);
    no raw stderr or prose parsing happens here.
    """
    return _inconsistencies_for(events)


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
    from ailuros.adapters.evidence_package.validator import (
        validate_evidence_package_contract,
    )

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
        inconsistencies=detect_evidence_inconsistencies(events),
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
        "inconsistencies": [
            {
                "rule_id": item.rule_id,
                "subject": item.subject,
                "values": list(item.values),
                "evidence_ids": list(item.evidence_ids),
            }
            for item in result.inconsistencies
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
    lines.append("")
    lines.append("| Inconsistency | Subject | Values | Evidence ids |")
    lines.append("|---|---|---|---|")
    if result.inconsistencies:
        for conflict in result.inconsistencies:
            values = ", ".join(conflict.values)
            ids = ", ".join(conflict.evidence_ids)
            lines.append(
                f"| {conflict.rule_id} | {conflict.subject} | {values} | {ids} |"
            )
    else:
        lines.append("| - | - | - | - |")
    return "\n".join(lines)
