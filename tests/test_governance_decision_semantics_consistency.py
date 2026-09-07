"""Cross-surface convergence of structured governance decision disposition.

Pack 8099: Ailuros carried two parallel decision-classification implementations.
``signals._evidence_inconsistency_rule`` hard-coded ``allow`` against
``{block, fail, blocked, deny}``, while post-run evidence conformance used the
projection approval vocabularies ``{approved, approve, granted}`` and
``{denied, deny, rejected, reject, declined}``.  The same structured token could
therefore be classified differently depending on which surface evaluated it.

Both surfaces now consume one shared primitive over one closed union
vocabulary.  Unknown tokens stay unknown on both sides.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ailuros.evidence_conformance import detect_evidence_inconsistencies
from ailuros.evidence_normalization import (
    DecisionDisposition,
    classify_decision_token,
)
from ailuros.projection import build_execution_projection
from ailuros.signals import _evidence_inconsistency_rule

_APPROVED_TOKENS = ("allow", "approved", "approve", "granted")
_DENIED_TOKENS = (
    "block",
    "fail",
    "blocked",
    "deny",
    "denied",
    "rejected",
    "reject",
    "declined",
)


# ── The shared primitive ─────────────────────────────────────────────────


@pytest.mark.parametrize("token", _APPROVED_TOKENS)
def test_shared_classifier_recognizes_the_approved_union(token: str) -> None:
    assert classify_decision_token(token) is DecisionDisposition.APPROVED


@pytest.mark.parametrize("token", _DENIED_TOKENS)
def test_shared_classifier_recognizes_the_denied_union(token: str) -> None:
    assert classify_decision_token(token) is DecisionDisposition.DENIED


@pytest.mark.parametrize(
    "value",
    ["escalate", "pending", "", "   ", None, True, False, 1, 0, ["allow"]],
)
def test_unrecognized_values_stay_unknown(value: object) -> None:
    assert classify_decision_token(value) is DecisionDisposition.UNKNOWN


def test_classification_is_trim_and_case_insensitive() -> None:
    assert classify_decision_token("  Approved ") is DecisionDisposition.APPROVED
    assert classify_decision_token("BLOCK") is DecisionDisposition.DENIED


def test_vocabulary_union_is_closed() -> None:
    # No synonym beyond the union of the two previously recognized sets.
    recognized = {
        t
        for t in _APPROVED_TOKENS + _DENIED_TOKENS
        if classify_decision_token(t) is not DecisionDisposition.UNKNOWN
    }
    assert recognized == set(_APPROVED_TOKENS) | set(_DENIED_TOKENS)
    for invented in ("accepted", "refused", "permitted", "forbidden", "ok"):
        assert classify_decision_token(invented) is DecisionDisposition.UNKNOWN


# ── Surface helpers ──────────────────────────────────────────────────────


def _signals_conflict(first: str, second: str) -> bool:
    """Does the signals surface see these two decisions as contradictory?

    The projection is built through the production path so the assertion covers
    real governance_decision evidence, not a hand-assembled model.
    """
    events: list[dict] = [
        {
            "event_id": "e0",
            "event_type": "run_started",
            "timestamp": datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
            "payload": {},
        }
    ]
    events += [
        {
            "event_id": f"e{index}",
            "event_type": "governance_decision",
            "timestamp": datetime(2026, 9, 1, 9, index, tzinfo=UTC),
            "scope_ref": "s1",
            # A fixed explicit domain keeps both decisions in one comparison
            # bucket: this pack converges decision *interpretation*, not the
            # separate projected-domain routing.
            "payload": {"domain": "execution_control", "decision": decision},
        }
        for index, decision in enumerate((first, second), start=1)
    ]
    projection = build_execution_projection("run-1", "external", events)
    return bool(_evidence_inconsistency_rule(projection))


def _conformance_conflict(first: str, second: str) -> bool:
    """Does the conformance surface see these two decisions as contradictory?"""
    events = [
        {
            "event_id": f"e{index}",
            "event_type": "approval_evidence",
            "payload": {"subject": "deploy", "action": "write", "decision": decision},
        }
        for index, decision in enumerate((first, second), start=1)
    ]
    findings = detect_evidence_inconsistencies(events)
    return any(f.subject == "deploy/write" for f in findings)


# ── Cross-surface convergence ────────────────────────────────────────────


@pytest.mark.parametrize("approved", _APPROVED_TOKENS)
@pytest.mark.parametrize("denied", _DENIED_TOKENS)
def test_every_union_pair_contradicts_on_both_surfaces(
    approved: str, denied: str
) -> None:
    assert _signals_conflict(approved, denied)
    assert _conformance_conflict(approved, denied)


def test_token_previously_known_only_to_signals_now_converges() -> None:
    # "allow" and "blocked"/"fail" were signals-only vocabulary; conformance
    # used to ignore them entirely.
    assert _signals_conflict("allow", "fail")
    assert _conformance_conflict("allow", "fail")


def test_token_previously_known_only_to_conformance_now_converges() -> None:
    # "granted"/"rejected" were conformance-only vocabulary; signals used to
    # ignore them entirely.
    assert _signals_conflict("granted", "rejected")
    assert _conformance_conflict("granted", "rejected")


# ── Unknown and missing evidence stay non-contradictory ──────────────────


def test_unknown_token_creates_no_contradiction_on_either_surface() -> None:
    assert not _signals_conflict("allow", "escalate")
    assert not _conformance_conflict("allow", "escalate")
    assert not _signals_conflict("escalate", "pending")
    assert not _conformance_conflict("escalate", "pending")


def test_agreeing_decisions_create_no_contradiction() -> None:
    assert not _signals_conflict("allow", "approved")
    assert not _conformance_conflict("allow", "approved")
    assert not _signals_conflict("deny", "blocked")
    assert not _conformance_conflict("deny", "blocked")


def test_missing_decision_field_is_not_a_contradiction() -> None:
    events = [
        {
            "event_id": "e1",
            "event_type": "approval_evidence",
            "payload": {"subject": "deploy", "action": "write", "decision": "allow"},
        },
        {
            "event_id": "e2",
            "event_type": "approval_evidence",
            "payload": {"subject": "deploy", "action": "write"},
        },
    ]
    assert not any(
        f.subject == "deploy/write" for f in detect_evidence_inconsistencies(events)
    )
