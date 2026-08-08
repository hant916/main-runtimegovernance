from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ailuros.storage import SQLiteStorage


class FleetOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_start: datetime
    window_end: datetime
    total_runs: int = 0
    outcomes: dict[str, int] = Field(default_factory=dict)
    validations: dict[str, int] = Field(default_factory=dict)
    scopes: dict[str, int] = Field(default_factory=dict)
    fallback_count: int = 0
    fallback_rate: float = 0.0
    signals: dict[str, int] = Field(default_factory=dict)
    sources: dict[str, int] = Field(default_factory=dict)
    source_filter: str | None = None

    @field_validator("window_start", "window_end")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value


_FALLBACK_SIGNAL_TYPES: frozenset[str] = frozenset({"backend_fallback", "backend_unavailable"})


def build_fleet_overview(
    storage: SQLiteStorage,
    window_start: datetime,
    window_end: datetime,
    source: str | None = None,
) -> FleetOverview:
    projections = storage.list_projections_in_window(window_start, window_end, source)

    total_runs = len(projections)
    outcomes: dict[str, int] = {}
    validations: dict[str, int] = {}
    scopes: dict[str, int] = {}
    sources: dict[str, int] = {}

    run_ids: list[str] = []
    for proj in projections:
        run_id = proj["run_id"]
        run_ids.append(run_id)

        src = proj.get("source") or "unknown"
        sources[src] = sources.get(src, 0) + 1

        outcome = proj.get("outcome_summary") or "unknown"
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

        validation = proj.get("validation_summary") or "unknown"
        validations[validation] = validations.get(validation, 0) + 1

        proj_json: dict[str, Any] | None = proj.get("projection")
        if isinstance(proj_json, dict):
            scope_val: str = proj_json.get("scope") or "unknown"
        else:
            scope_val = "unknown"
        scopes[scope_val] = scopes.get(scope_val, 0) + 1

    fallback_count = 0
    signal_counts: dict[str, int] = {}
    if run_ids:
        all_signals = storage.list_signals_for_runs(run_ids)
        for sig in all_signals:
            sig_type: str = sig.get("type", "unknown")
            signal_counts[sig_type] = signal_counts.get(sig_type, 0) + 1
            if sig_type in _FALLBACK_SIGNAL_TYPES:
                fallback_count += 1

    fallback_rate = fallback_count / total_runs if total_runs > 0 else 0.0

    return FleetOverview(
        window_start=window_start,
        window_end=window_end,
        total_runs=total_runs,
        outcomes=outcomes,
        validations=validations,
        scopes=scopes,
        fallback_count=fallback_count,
        fallback_rate=fallback_rate,
        signals=signal_counts,
        sources=sources,
        source_filter=source,
    )
