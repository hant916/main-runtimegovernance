"""Shared normalization of valid external evidence wrapper events."""

from __future__ import annotations

from typing import Any


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
