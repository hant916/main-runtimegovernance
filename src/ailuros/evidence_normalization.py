"""Shared normalization and recognition of canonical governance evidence.

This module is the single source-neutral interpretation boundary for evidence:
it turns valid ``external_evidence`` wrapper events into their canonical form
and exposes the one small recognition primitive that tells callers which event
types are already established as canonical governance evidence by Ailuros
capability evaluation and projection.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from ailuros._compat import StrEnum

# Canonical governance-evidence event types already consumed by capability
# conformance (``_CAPABILITY_SPECS``) and by the execution projection. This is a
# *recognition* boundary, not an execution/runtime vocabulary: RuntimeEventType
# remains the runtime event enum, and these additional governance evidence types
# are recognized separately so the structural validator and capability
# conformance agree instead of the validator calling canonical evidence unknown.
_CANONICAL_GOVERNANCE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "run_started",
        "run_completed",
        "run_failed",
        "governance_decision",
        "project_scope",
        "project_validation",
        "runtime_role",
        "governance_context",
        "authority_evidence",
        "approval_evidence",
        "budget_evidence",
    }
)


class DecisionDisposition(StrEnum):
    """What a structured governance decision token means, if anything.

    ``UNKNOWN`` is the honest answer for a token outside the closed vocabulary,
    for a missing field and for any non-string value.  It never stands in for a
    contradiction: two claims only disagree when both classify.
    """

    APPROVED = "approved"
    DENIED = "denied"
    UNKNOWN = "unknown"


# The closed governance decision vocabulary, shared by every Ailuros surface
# that interprets a decision token.  These sets are the union of the vocabularies
# the signals and conformance surfaces previously maintained separately; nothing
# beyond that union is recognized, because a synonym Ailuros invents is a claim
# no producer made.
_APPROVED_DECISION_TOKENS: frozenset[str] = frozenset(
    {"allow", "approved", "approve", "granted"}
)

_DENIED_DECISION_TOKENS: frozenset[str] = frozenset(
    {"block", "fail", "blocked", "deny", "denied", "rejected", "reject", "declined"}
)


def classify_decision_token(value: Any) -> DecisionDisposition:
    """Classify one structured decision token as approved, denied or unknown.

    This is the single semantic boundary for decision disposition: signals-side
    inconsistency detection, post-run conformance and projection approval-state
    normalization all read it, so the same structured token cannot mean
    different things on different Ailuros surfaces.

    Only structured strings participate, compared after trim+lowercase.  No
    prose is parsed, no synonym is inferred, and booleans and other non-string
    values are never decisions.
    """
    if not isinstance(value, str):
        return DecisionDisposition.UNKNOWN
    token = value.strip().lower()
    if token in _APPROVED_DECISION_TOKENS:
        return DecisionDisposition.APPROVED
    if token in _DENIED_DECISION_TOKENS:
        return DecisionDisposition.DENIED
    return DecisionDisposition.UNKNOWN


def canonical_governance_event_types() -> frozenset[str]:
    """Return the shared, source-neutral recognition boundary for canonical
    governance evidence already supported by Ailuros capability evaluation.

    Producer/source identity never enters this boundary: a type is recognized
    or not solely on its canonical event_type name.
    """
    return _CANONICAL_GOVERNANCE_EVENT_TYPES


def normalize_external_evidence_event(event: dict[str, Any]) -> dict[str, Any]:
    """Return a canonical view of a valid ``external_evidence`` wrapper.

    Malformed or partial wrappers are returned unchanged.  Normalization is an
    interpretation boundary, not a repair mechanism, so it must never invent
    evidence fields.

    Metadata follows a single fallback rule: a dict on the inner wrapper wins
    exactly as supplied, and otherwise valid envelope metadata is preserved
    instead of being discarded.  The two are never merged.
    """
    if event.get("event_type") != "external_evidence":
        return event

    wrapper = event.get("payload")
    if not isinstance(wrapper, dict):
        return event

    event_type = wrapper.get("event_type")
    payload = wrapper.get("payload")
    if not isinstance(event_type, str) or not event_type or not isinstance(payload, dict):
        return event

    normalized = event.copy()
    normalized["event_type"] = event_type
    normalized["payload"] = payload
    metadata = wrapper.get("metadata")
    if not isinstance(metadata, dict):
        # The inner wrapper carries no metadata dict: fall back to metadata the
        # envelope already supplied rather than erasing it.  Provenance such as
        # ``metadata.artifact`` must survive normalization for the existing
        # EvidenceRef path; the two dicts are never merged.
        outer_metadata = event.get("metadata")
        metadata = outer_metadata if isinstance(outer_metadata, dict) else {}
    normalized["metadata"] = metadata
    scope_ref = wrapper.get("scope_ref")
    if isinstance(scope_ref, str) and scope_ref:
        normalized["scope_ref"] = scope_ref
    return normalized


def _partial_time(event: dict[str, Any]) -> time | None:
    """Return an ordered partial-time marker for events lacking a full date.

    Accepts a ``datetime.time`` or an ISO ``HH:MM[:SS]`` string under the
    ``partial_time`` key.  Anything else means there is no partial-time evidence
    to interpret.
    """
    raw = event.get("partial_time")
    if isinstance(raw, time):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return time.fromisoformat(raw)
        except ValueError:
            return None
    return None


# Only a backward wall-clock movement larger than this can be read as crossing
# midnight.  A smaller (or exactly equal) step back is ordinary evidence
# disorder: reporting it is honest, dating it a day later would be invented.
_MIDNIGHT_WRAP_MIN_BACKWARD = timedelta(hours=12)


def _is_midnight_wrap(prev_tod: time, current_tod: time) -> bool:
    """Return whether ``prev_tod`` -> ``current_tod`` is a deterministic wrap.

    The only partial-time movement treated as a midnight crossing is a backward
    wall-clock jump strictly greater than 12 hours (e.g. ``23:53`` -> ``00:53``).
    Anything else — including an exact 12-hour step back — remains ambiguous and
    is surfaced as a chronology regression instead of a new calendar day.
    """
    if current_tod >= prev_tod:
        return False
    backward = datetime.combine(date.min, prev_tod) - datetime.combine(
        date.min, current_tod
    )
    return backward > _MIDNIGHT_WRAP_MIN_BACKWARD


def normalize_timeline_timestamps(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Attach derived dates to partial-time events and flag chronology regressions.

    This is the single normalization boundary that turns ordered source events
    into normalized timeline events.  It does not reorder events and it never
    rewrites explicit full timestamps.

    Behaviour:

    * An event carrying an explicit ``timestamp`` (:class:`datetime`) is passed
      through unchanged and anchors the derived calendar date for any following
      partial-time evidence.
    * An event carrying only ``partial_time`` has a date attached by carrying the
      previous derived date forward.  The date is incremented only for a
      *large* backward wall-clock wrap (more than 12 hours, e.g. ``23:53``
      followed by ``00:53``), which is the sole partial-time movement that
      deterministically represents crossing midnight.  Ordinary backward jitter
      (a 12-hour or smaller step back, e.g. ``10:00:05`` -> ``10:00:03`` or
      ``00:53`` -> ``00:10``) stays on the carried date and is reported as a
      chronology regression rather than fabricating a later calendar day.
    * A partial-time event with no preceding date anchor is ambiguous: no date is
      fabricated, the condition is reported as a regression, and the event never
      becomes trusted inference state for later events.
    * Any remaining non-monotonic timestamp after deterministic normalization
      (for example explicit dated timestamps that move backwards) is reported as
      a regression without being rewritten or reordered.

    Returns ``(normalized_events, regressions)`` where ``normalized_events``
    preserves input order and ``regressions`` lists the unresolved conditions.
    """
    normalized: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []

    carried_date: date | None = None
    carried_tz: Any = None
    prev_tod: time | None = None
    prev_dt: datetime | None = None

    for event in events:
        new_event = dict(event)
        timestamp = event.get("timestamp")
        derived_dt: datetime | None = None

        if isinstance(timestamp, datetime):
            # Explicit full timestamp: preserved exactly, anchors the date.
            carried_date = timestamp.date()
            carried_tz = timestamp.tzinfo
            prev_tod = timestamp.time()
            derived_dt = timestamp
        else:
            partial = _partial_time(event)
            if partial is None:
                # No timestamp and no partial-time evidence: nothing to derive.
                normalized.append(new_event)
                continue
            partial_tod = partial.replace(tzinfo=None)
            if carried_date is None:
                # Ambiguous: no anchor date to attach; do not invent one.
                new_event["timestamp"] = None
                normalized.append(new_event)
                regressions.append(
                    {
                        "event_id": event.get("event_id", ""),
                        "reason": "ambiguous_partial_time_no_anchor",
                    }
                )
                # Unanchored evidence stays ambiguous: it must not become the
                # trusted state that later anchored derivation reasons from.
                continue
            if prev_tod is not None and _is_midnight_wrap(prev_tod, partial_tod):
                # Deterministic midnight rollover: increment the derived date.
                carried_date = carried_date + timedelta(days=1)
            tzinfo = partial.tzinfo or carried_tz
            derived_dt = datetime.combine(carried_date, partial_tod, tzinfo=tzinfo)
            new_event["timestamp"] = derived_dt
            prev_tod = partial_tod

        normalized.append(new_event)

        if prev_dt is not None and derived_dt is not None:
            try:
                backwards = derived_dt < prev_dt
            except TypeError:
                backwards = False
            if backwards:
                regressions.append(
                    {
                        "event_id": event.get("event_id", ""),
                        "reason": "non_monotonic_timestamp",
                        "previous": prev_dt.isoformat(),
                        "current": derived_dt.isoformat(),
                    }
                )
        if derived_dt is not None:
            prev_dt = derived_dt

    return normalized, regressions
