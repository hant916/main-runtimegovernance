"""Regression coverage for deterministic timeline midnight integrity.

Covers the four contract layers of pack 8094:
  * same-day monotonic events (no rollover, no warning),
  * deterministic cross-midnight rollover (next-day date derived),
  * explicit non-monotonic dated timestamps (preserved + warned),
  * ambiguous partial-time chronology (no invented date + warned),
plus the invariant that event order always matches input order.
"""

from __future__ import annotations

from datetime import UTC, datetime, time

from ailuros.evidence_normalization import normalize_timeline_timestamps
from ailuros.signals import build_temporal_integrity_signals


def _ts(hour: int, minute: int, day: int = 1) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=UTC)


def _ids(events: list[dict]) -> list[str]:
    return [e["event_id"] for e in events]


# ── Same-day monotonic ───────────────────────────────────────────────────


def test_same_day_monotonic_partials_no_rollover_no_warning() -> None:
    events = [
        {"event_id": "e1", "timestamp": _ts(9, 0)},
        {"event_id": "e2", "partial_time": time(10, 0)},
        {"event_id": "e3", "partial_time": time(11, 30)},
    ]
    normalized, regressions = normalize_timeline_timestamps(events)

    assert regressions == []
    assert _ids(normalized) == ["e1", "e2", "e3"]
    assert normalized[1]["timestamp"] == _ts(10, 0)
    assert normalized[2]["timestamp"] == _ts(11, 30)


def test_explicit_monotonic_timestamps_are_untouched() -> None:
    events = [
        {"event_id": "e1", "timestamp": _ts(9, 0)},
        {"event_id": "e2", "timestamp": _ts(9, 1)},
        {"event_id": "e3", "timestamp": _ts(9, 2)},
    ]
    normalized, regressions = normalize_timeline_timestamps(events)

    assert regressions == []
    assert [e["timestamp"] for e in normalized] == [_ts(9, 0), _ts(9, 1), _ts(9, 2)]


# ── Deterministic cross-midnight rollover ────────────────────────────────


def test_cross_midnight_partial_rolls_to_next_day() -> None:
    events = [
        {"event_id": "e1", "timestamp": _ts(23, 53)},
        {"event_id": "e2", "partial_time": time(0, 53)},
    ]
    normalized, regressions = normalize_timeline_timestamps(events)

    # 23:53 -> 00:53 deterministically represents a midnight rollover.
    assert regressions == []
    assert normalized[0]["timestamp"] == _ts(23, 53, day=1)
    assert normalized[1]["timestamp"] == _ts(0, 53, day=2)
    # The explicit anchor timestamp is preserved exactly.
    assert normalized[0]["timestamp"] == events[0]["timestamp"]
    assert _ids(normalized) == ["e1", "e2"]


def test_cross_midnight_does_not_render_time_backwards_same_day() -> None:
    events = [
        {"event_id": "e1", "timestamp": _ts(23, 53)},
        {"event_id": "e2", "partial_time": time(0, 53)},
    ]
    normalized, _ = normalize_timeline_timestamps(events)

    # The derived timeline is strictly forward, never same-day backward time.
    assert normalized[1]["timestamp"] > normalized[0]["timestamp"]


# ── Explicit non-monotonic dated timestamps ──────────────────────────────


def test_explicit_non_monotonic_preserved_and_warned() -> None:
    events = [
        {"event_id": "e1", "timestamp": _ts(10, 0)},
        {"event_id": "e2", "timestamp": _ts(9, 0)},
    ]
    normalized, regressions = normalize_timeline_timestamps(events)

    # Explicit timestamps are never rewritten to force monotonicity.
    assert normalized[0]["timestamp"] == _ts(10, 0)
    assert normalized[1]["timestamp"] == _ts(9, 0)
    assert _ids(normalized) == ["e1", "e2"]
    assert len(regressions) == 1
    assert regressions[0]["reason"] == "non_monotonic_timestamp"
    assert regressions[0]["event_id"] == "e2"


# ── Ambiguous partial-time chronology ────────────────────────────────────


def test_ambiguous_partial_time_without_anchor_is_not_invented() -> None:
    events = [
        {"event_id": "e1", "partial_time": time(14, 0)},
        {"event_id": "e2", "partial_time": time(15, 0)},
    ]
    normalized, regressions = normalize_timeline_timestamps(events)

    # No anchor date exists, so no date is fabricated.
    assert normalized[0]["timestamp"] is None
    assert normalized[1]["timestamp"] is None
    assert _ids(normalized) == ["e1", "e2"]
    reasons = {r["reason"] for r in regressions}
    assert reasons == {"ambiguous_partial_time_no_anchor"}


# ── Ordering invariant ───────────────────────────────────────────────────


def test_event_order_is_never_changed() -> None:
    events = [
        {"event_id": "e1", "timestamp": _ts(23, 0)},
        {"event_id": "e2", "partial_time": time(0, 30)},  # rollover
        {"event_id": "e3", "timestamp": _ts(8, 0)},  # explicit backwards -> warn
        {"event_id": "e4", "partial_time": time(9, 0)},
    ]
    normalized, regressions = normalize_timeline_timestamps(events)

    assert _ids(normalized) == _ids(events)
    # A regression is surfaced, but order is untouched (not reordered to hide it).
    assert any(r["reason"] == "non_monotonic_timestamp" for r in regressions)


def test_passthrough_events_without_time_evidence() -> None:
    events = [
        {"event_id": "e1", "timestamp": _ts(9, 0)},
        {"event_id": "e2"},  # no timestamp, no partial_time
        {"event_id": "e3", "partial_time": time(10, 0)},
    ]
    normalized, regressions = normalize_timeline_timestamps(events)

    assert _ids(normalized) == ["e1", "e2", "e3"]
    assert "timestamp" not in normalized[1]
    assert normalized[2]["timestamp"] == _ts(10, 0)
    assert regressions == []


# ── Warning surfacing via the existing signal mechanism ──────────────────


def test_temporal_integrity_signal_built_from_regressions() -> None:
    regressions = [
        {"event_id": "e2", "reason": "non_monotonic_timestamp"},
    ]
    signals = build_temporal_integrity_signals("run-1", regressions)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.type == "temporal_integrity"
    assert signal.subject == "timeline"
    assert signal.details["regressions"] == regressions
    assert [r.event_id for r in signal.evidence_refs] == ["e2"]


def test_no_temporal_integrity_signal_when_clean() -> None:
    assert build_temporal_integrity_signals("run-1", []) == []


def test_string_partial_time_is_supported() -> None:
    events = [
        {"event_id": "e1", "timestamp": _ts(23, 0)},
        {"event_id": "e2", "partial_time": "00:15"},
    ]
    normalized, regressions = normalize_timeline_timestamps(events)

    assert regressions == []
    assert normalized[1]["timestamp"] == _ts(0, 15, day=2)
