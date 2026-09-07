"""Regression coverage for external_evidence envelope metadata preservation.

Pack 8098: ``normalize_external_evidence_event`` used to replace normalized
metadata with the inner wrapper metadata or ``{}`` unconditionally, erasing a
producer-supplied *outer* ``metadata.artifact`` whenever the inner wrapper
omitted metadata.  That defeated the artifact-reference preservation path added
by pack 8095 (:func:`ailuros.projection._event_evidence_ref`).

The repair is deliberately narrow: inner dict metadata keeps precedence exactly
as before, and outer metadata is retained only as a fallback.  No merge policy,
no artifact resolution.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ailuros.evidence_normalization import normalize_external_evidence_event
from ailuros.projection import build_execution_projection


def _wrapper(
    *,
    outer_metadata: object = None,
    inner_metadata: object = None,
    event_id: str = "e1",
) -> dict:
    wrapper: dict = {"event_type": "run_started", "payload": {"run_id": "run-1"}}
    if inner_metadata is not None:
        wrapper["metadata"] = inner_metadata
    event: dict = {
        "event_id": event_id,
        "event_type": "external_evidence",
        "timestamp": datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        "payload": wrapper,
    }
    if outer_metadata is not None:
        event["metadata"] = outer_metadata
    return event


# ── Outer metadata fallback ──────────────────────────────────────────────


def test_outer_artifact_survives_when_inner_metadata_missing() -> None:
    event = _wrapper(outer_metadata={"artifact": "s3://bucket/run-1.json"})
    normalized = normalize_external_evidence_event(event)

    assert normalized["metadata"] == {"artifact": "s3://bucket/run-1.json"}
    assert normalized["event_type"] == "run_started"


def test_outer_pointer_survives_when_inner_metadata_missing() -> None:
    event = _wrapper(outer_metadata={"pointer": "line:42"})
    normalized = normalize_external_evidence_event(event)

    assert normalized["metadata"] == {"pointer": "line:42"}


def test_outer_metadata_survives_when_inner_metadata_is_not_a_dict() -> None:
    event = _wrapper(
        outer_metadata={"artifact": "file:///evidence.json"},
        inner_metadata="not-a-dict",
    )
    normalized = normalize_external_evidence_event(event)

    assert normalized["metadata"] == {"artifact": "file:///evidence.json"}


# ── Inner precedence is unchanged ────────────────────────────────────────


def test_inner_dict_metadata_keeps_precedence_without_merging() -> None:
    event = _wrapper(
        outer_metadata={"artifact": "outer://a", "pointer": "outer-pointer"},
        inner_metadata={"artifact": "inner://a"},
    )
    normalized = normalize_external_evidence_event(event)

    # Exactly the inner dict: no merge of the outer pointer.
    assert normalized["metadata"] == {"artifact": "inner://a"}


def test_empty_inner_dict_metadata_still_wins() -> None:
    event = _wrapper(outer_metadata={"artifact": "outer://a"}, inner_metadata={})
    normalized = normalize_external_evidence_event(event)

    assert normalized["metadata"] == {}


# ── Nothing is fabricated ────────────────────────────────────────────────


def test_non_dict_outer_metadata_yields_no_fabricated_values() -> None:
    event = _wrapper(outer_metadata="not-a-dict")
    normalized = normalize_external_evidence_event(event)

    assert normalized["metadata"] == {}


def test_absent_metadata_on_both_layers_stays_empty() -> None:
    event = _wrapper()
    normalized = normalize_external_evidence_event(event)

    assert normalized["metadata"] == {}


def test_malformed_wrapper_is_returned_unchanged() -> None:
    event = {
        "event_id": "e1",
        "event_type": "external_evidence",
        "metadata": {"artifact": "outer://a"},
        "payload": {"event_type": "run_started"},  # no inner payload dict
    }
    assert normalize_external_evidence_event(event) == event


# ── The preserved reference reaches the existing EvidenceRef path ────────


def test_outer_artifact_reaches_projection_evidence_ref() -> None:
    events = [_wrapper(outer_metadata={"artifact": "s3://bucket/run-1.json"})]
    projection = build_execution_projection("run-1", "external", events)

    refs = [r for r in projection.evidence_refs if r.event_id == "e1"]
    assert len(refs) == 1
    assert refs[0].artifact == "s3://bucket/run-1.json"


def test_inner_artifact_precedence_holds_through_projection() -> None:
    events = [
        _wrapper(
            outer_metadata={"artifact": "outer://a"},
            inner_metadata={"artifact": "inner://a"},
        )
    ]
    projection = build_execution_projection("run-1", "external", events)

    refs = [r for r in projection.evidence_refs if r.event_id == "e1"]
    assert refs[0].artifact == "inner://a"
