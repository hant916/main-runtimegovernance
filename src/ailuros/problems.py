from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ailuros.core.execution import EvidenceRef


class TrendBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    count: int


class ProblemGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_type: str
    subject_key: str
    count: int
    affected_run_ids: list[str]
    first_seen: datetime
    last_seen: datetime
    severity_counts: dict[str, int] = Field(default_factory=dict)
    trend_buckets: list[TrendBucket] = Field(default_factory=list)


class ContributingSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    run_id: str
    severity: str
    evidence_refs: list[EvidenceRef]
    created_at: datetime


class ProblemDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_type: str
    subject_key: str
    group: ProblemGroup
    contributing_signals: list[ContributingSignal]


def _build_daily_buckets(
    signals: list[dict[str, Any]],
    first_seen: datetime,
    last_seen: datetime,
) -> list[TrendBucket]:
    start_date = first_seen.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = last_seen.replace(hour=0, minute=0, second=0, microsecond=0)
    day_counts: dict[str, int] = defaultdict(int)
    for s in signals:
        created = s["created_at"]
        if isinstance(created, datetime):
            day_label = created.strftime("%Y-%m-%d")
            day_counts[day_label] += 1
    buckets: list[TrendBucket] = []
    current = start_date
    while current <= end_date:
        label = current.strftime("%Y-%m-%d")
        buckets.append(TrendBucket(label=label, count=day_counts.get(label, 0)))
        current += timedelta(days=1)
    return buckets


def _signal_grouping_key(signal: dict[str, Any]) -> tuple[str, str]:
    return (signal["type"], signal["subject"])


def aggregate_problems(
    storage: Any,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    source: str | None = None,
) -> list[ProblemGroup]:
    signals = storage.list_signals_in_window(
        window_start=window_start,
        window_end=window_end,
        source=source,
    )

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for s in signals:
        key = _signal_grouping_key(s)
        groups[key].append(s)

    result: list[ProblemGroup] = []
    for (sig_type, subject), sig_list in groups.items():
        sig_list.sort(key=lambda s: s["created_at"])
        first_seen = sig_list[0]["created_at"]
        last_seen = sig_list[-1]["created_at"]

        severity_counts: dict[str, int] = defaultdict(int)
        affected_ids: set[str] = set()
        for s in sig_list:
            severity_counts[s["severity"]] += 1
            affected_ids.add(s["run_id"])

        result.append(
            ProblemGroup(
                signal_type=sig_type,
                subject_key=subject,
                count=len(sig_list),
                affected_run_ids=sorted(affected_ids),
                first_seen=first_seen,
                last_seen=last_seen,
                severity_counts=dict(severity_counts),
                trend_buckets=_build_daily_buckets(sig_list, first_seen, last_seen),
            )
        )

    result.sort(key=lambda g: (-g.count, g.last_seen), reverse=False)
    return result


def get_problem_detail(
    storage: Any,
    signal_type: str,
    subject_key: str,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    source: str | None = None,
) -> ProblemDetail:
    signals = storage.list_signals_in_window(
        window_start=window_start,
        window_end=window_end,
        source=source,
    )

    matching = [
        s
        for s in signals
        if s["type"] == signal_type and s["subject"] == subject_key
    ]
    matching.sort(key=lambda s: s["created_at"])

    if not matching:
        raise LookupError(
            f"no signals found for type={signal_type} subject={subject_key}"
        )

    first_seen = matching[0]["created_at"]
    last_seen = matching[-1]["created_at"]

    severity_counts: dict[str, int] = defaultdict(int)
    affected_ids: set[str] = set()
    for s in matching:
        severity_counts[s["severity"]] += 1
        affected_ids.add(s["run_id"])

    group = ProblemGroup(
        signal_type=signal_type,
        subject_key=subject_key,
        count=len(matching),
        affected_run_ids=sorted(affected_ids),
        first_seen=first_seen,
        last_seen=last_seen,
        severity_counts=dict(severity_counts),
        trend_buckets=_build_daily_buckets(matching, first_seen, last_seen),
    )

    contributing = [
        ContributingSignal(
            signal_id=s["signal_id"],
            run_id=s["run_id"],
            severity=s["severity"],
            evidence_refs=[
                EvidenceRef(**r) if isinstance(r, dict) else r
                for r in s.get("evidence_refs", [])
            ],
            created_at=s["created_at"],
        )
        for s in matching
    ]

    return ProblemDetail(
        signal_type=signal_type,
        subject_key=subject_key,
        group=group,
        contributing_signals=contributing,
    )
