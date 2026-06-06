from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ailuros._compat import StrEnum


class AuditDecision(StrEnum):
    """Post-run audit decision.

    Exactly three values are defined. These describe the *outcome of validating
    an already-completed run's evidence*; they are not runtime control actions.
    """

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class AuditResult(BaseModel):
    """Generic, source-neutral result of a post-run audit.

    The audit consumes a completed run's canonical evidence package and reports a
    pass/warn/fail :class:`AuditDecision`. It performs no runtime control: there
    is no allow/review/block path here, only an after-the-fact judgement about
    whether the captured evidence is clean (``pass``), has tolerated anomalies
    (``warn``), or is invalid (``fail``).
    """

    model_config = ConfigDict(extra="forbid")

    ok: bool
    decision: AuditDecision
    governance_mode: str | None = None
    source: str | None = None
    schema_version: str | None = None
    run_id: str | None = None
    events_count: int | None = None
    rules_evaluated: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
