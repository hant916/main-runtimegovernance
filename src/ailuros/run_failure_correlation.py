from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ailuros._compat import StrEnum
from ailuros.core.execution import EvidenceRef
from ailuros.run_diagnosis import IncompleteWork, NextAction, RootCause, RunDiagnosis


class RecurrenceState(StrEnum):
    """Bounded recurrence classification over the supplied run set.

    ``recurrent`` is proven only by two or more equivalent structured failure
    signatures. ``unproven`` means a run failed without enough structured
    fields to prove equivalence, so recurrence is never matched by prose.
    """

    NONE = "none"
    SINGLE = "single"
    RECURRENT = "recurrent"
    UNPROVEN = "unproven"


class RetrySafety(StrEnum):
    """Advisory retry-safety classification for a blind coder retry.

    ``unsafe`` is reserved for repeated runtime/process-supervision signatures;
    it never implies a specific vendor/API/OOM cause and never overrides
    per-diagnosis validation, scope, or acceptance guidance.
    """

    SAFE = "safe"
    UNSAFE = "unsafe"
    UNPROVEN = "unproven"


class FailureSignature(BaseModel):
    """Bounded structured signature for one failed run.

    Built exclusively from closed diagnosis fields (root-cause class and its
    structured sub-cause code). Timestamps, run ids, vendor prose, and
    incidental payload fields are excluded so equivalent canonical facts yield
    identical signatures regardless of producer source labels.
    """

    model_config = ConfigDict(extra="forbid")

    root_cause: RootCause
    root_cause_detail: str = "unknown"


class FailureGroup(BaseModel):
    """One distinct structured failure signature and its occurrences."""

    model_config = ConfigDict(extra="forbid")

    signature: FailureSignature
    count: int
    run_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class FailureCorrelation(BaseModel):
    """Bounded recurrence correlation over a caller-supplied diagnosis set.

    Advisory and read-only: it never edits a pack, widens scope, mutates
    runtime state, or returns ACCEPT. Input cardinality is exactly the supplied
    list; no database, history scan, background monitor, or durable memory is
    consulted.
    """

    model_config = ConfigDict(extra="forbid")

    run_ids: list[str] = Field(default_factory=list)
    recurrence: RecurrenceState = RecurrenceState.NONE
    groups: list[FailureGroup] = Field(default_factory=list)
    unproven_run_ids: list[str] = Field(default_factory=list)
    retry_safety: RetrySafety = RetrySafety.SAFE
    recommendation: NextAction = NextAction.NONE
    recommendation_note: str = ""

    @property
    def recurrence_count(self) -> int:
        """Count of the most frequent structured failure signature."""
        if not self.groups:
            return 0
        return self.groups[0].count


_RUNTIME_CAUSES: frozenset[RootCause] = frozenset(
    {RootCause.EXECUTION_RUNTIME_PROCESS_SUPERVISION}
)


def failure_signature(diagnosis: RunDiagnosis) -> FailureSignature | None:
    """Derive a bounded structured failure signature from one diagnosis.

    Returns ``None`` when the diagnosis carries no incomplete work or when its
    root-cause class is unknown (insufficient structured fields for
    equivalence). No free-form prose is ever read.
    """
    if diagnosis.incomplete == IncompleteWork.NONE:
        return None
    if diagnosis.root_cause == RootCause.UNKNOWN:
        return None
    return FailureSignature(
        root_cause=diagnosis.root_cause,
        root_cause_detail=diagnosis.root_cause_detail,
    )


def _dedupe_sorted_refs(refs: list[EvidenceRef]) -> list[EvidenceRef]:
    seen: set[str] = set()
    out: list[EvidenceRef] = []
    for ref in refs:
        if ref.event_id in seen:
            continue
        seen.add(ref.event_id)
        out.append(ref)
    out.sort(key=lambda ref: ref.event_id)
    return out


def _group_order_key(group: FailureGroup) -> tuple[int, str, str]:
    return (
        -group.count,
        group.signature.root_cause.value,
        group.signature.root_cause_detail,
    )


def _is_runtime_group(group: FailureGroup) -> bool:
    return group.signature.root_cause in _RUNTIME_CAUSES


def _build_note(
    *,
    runtime_group: FailureGroup | None,
    has_unproven: bool,
    groups: list[FailureGroup],
) -> str:
    if runtime_group is not None:
        runs = ", ".join(runtime_group.run_ids)
        return (
            f"{runtime_group.count} equivalent "
            f"{runtime_group.signature.root_cause.value} failures recur across "
            f"run(s) {runs} with no evidence of a corrective state change. A further "
            "blind coder retry is unsafe/ineffective; stop spending coder executions "
            "and repair the runtime boundary. No specific vendor/API/OOM cause is "
            "inferred."
        )
    if has_unproven:
        return (
            "Cannot prove recurrence from structured facts: at least one run failed "
            "without a proven failure class. Route to human review rather than "
            "inventing a remediation."
        )
    if any(group.count >= 2 for group in groups):
        return (
            "Recurrence is limited to non-runtime failure classes; per-run diagnoses "
            "already recommend their bounded actions and no runtime escalation "
            "applies."
        )
    if groups:
        return (
            "No equivalent failure signature recurs across the supplied run set; "
            "per-run diagnoses keep their own bounded recommendations."
        )
    return "No failure signatures to correlate."


def correlate_run_failures(diagnoses: list[RunDiagnosis]) -> FailureCorrelation:
    """Correlate structured failure signatures across a bounded run set.

    The input is exactly the list supplied by the caller; no additional runs are
    discovered. Each diagnosis yields a structured signature, equivalent
    signatures are grouped deterministically, and repeated runtime/
    process-supervision signatures escalate retry guidance to
    ``repair_runtime`` instead of another blind coder retry.
    """
    groups: dict[tuple[str, str], FailureGroup] = {}
    group_run_ids: dict[tuple[str, str], set[str]] = {}
    unproven_run_ids: list[str] = []
    seen_run_ids: set[str] = set()
    run_ids: list[str] = []

    for diagnosis in diagnoses:
        if diagnosis.run_id not in seen_run_ids:
            seen_run_ids.add(diagnosis.run_id)
            run_ids.append(diagnosis.run_id)
        signature = failure_signature(diagnosis)
        if signature is None:
            if diagnosis.incomplete != IncompleteWork.NONE:
                unproven_run_ids.append(diagnosis.run_id)
            continue
        key = (signature.root_cause.value, signature.root_cause_detail)
        group = groups.get(key)
        if group is None:
            group = FailureGroup(signature=signature, count=0, run_ids=[], evidence_refs=[])
            groups[key] = group
            group_run_ids[key] = set()
        distinct = group_run_ids[key]
        if diagnosis.run_id not in distinct:
            distinct.add(diagnosis.run_id)
            group.count += 1
            group.run_ids.append(diagnosis.run_id)
        for ref in diagnosis.evidence_refs:
            if not any(existing.event_id == ref.event_id for existing in group.evidence_refs):
                group.evidence_refs.append(ref)

    ordered_groups = sorted(groups.values(), key=_group_order_key)
    for group in ordered_groups:
        group.evidence_refs = _dedupe_sorted_refs(group.evidence_refs)

    has_unproven = bool(unproven_run_ids)
    any_recurrent = any(group.count >= 2 for group in ordered_groups)
    if any_recurrent:
        recurrence = RecurrenceState.RECURRENT
    elif has_unproven:
        recurrence = RecurrenceState.UNPROVEN
    elif ordered_groups:
        recurrence = RecurrenceState.SINGLE
    else:
        recurrence = RecurrenceState.NONE

    runtime_group = next(
        (group for group in ordered_groups if group.count >= 2 and _is_runtime_group(group)),
        None,
    )

    if runtime_group is not None:
        retry_safety = RetrySafety.UNSAFE
        recommendation = NextAction.REPAIR_RUNTIME
    elif has_unproven:
        retry_safety = RetrySafety.UNPROVEN
        recommendation = NextAction.HUMAN_REVIEW
    else:
        retry_safety = RetrySafety.SAFE
        recommendation = NextAction.NONE

    return FailureCorrelation(
        run_ids=run_ids,
        recurrence=recurrence,
        groups=ordered_groups,
        unproven_run_ids=unproven_run_ids,
        retry_safety=retry_safety,
        recommendation=recommendation,
        recommendation_note=_build_note(
            runtime_group=runtime_group,
            has_unproven=has_unproven,
            groups=ordered_groups,
        ),
    )


def render_correlation_json(correlation: FailureCorrelation) -> str:
    return correlation.model_dump_json(indent=2)


def render_correlation_markdown(correlation: FailureCorrelation) -> str:
    lines: list[str] = []

    lines.append("# Run Failure Correlation")
    lines.append("")

    lines.append("## Recurrence")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Runs | {', '.join(correlation.run_ids) or 'none'} |")
    lines.append(f"| Recurrence | {correlation.recurrence.value} |")
    lines.append(f"| Recurrence Count | {correlation.recurrence_count} |")
    lines.append(f"| Retry Safety | {correlation.retry_safety.value} |")
    lines.append(f"| Recommendation | {correlation.recommendation.value} |")
    lines.append("")

    if correlation.groups:
        lines.append("## Failure Signatures")
        lines.append("")
        lines.append("| Root Cause | Detail | Count | Runs |")
        lines.append("|---|---|---|---|")
        for group in correlation.groups:
            runs = ", ".join(group.run_ids)
            lines.append(
                f"| {group.signature.root_cause.value} | "
                f"{group.signature.root_cause_detail} | {group.count} | {runs} |"
            )
        lines.append("")

    if correlation.unproven_run_ids:
        lines.append("## Unproven Runs")
        lines.append("")
        lines.append(", ".join(correlation.unproven_run_ids))
        lines.append("")

    if correlation.recommendation_note:
        lines.append("## Advisory Note")
        lines.append("")
        lines.append(correlation.recommendation_note)
        lines.append("")

    return "\n".join(lines)
