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
    normalized["metadata"] = metadata if isinstance(metadata, dict) else {}
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
      previous derived date forward.  When ordered partial-time evidence steps
      backwards in wall-clock time (e.g. ``23:53`` followed by ``00:53``) that
      deterministically represents a midnight rollover, so the derived date is
      incremented by one day.
    * A partial-time event with no preceding date anchor is ambiguous: no date is
      fabricated and the condition is reported as a regression.
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
                prev_tod = partial_tod
                continue
            if prev_tod is not None and partial_tod < prev_tod:
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
