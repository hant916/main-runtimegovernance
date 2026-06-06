from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ValidationResult(BaseModel):
    """Generic, source-neutral outcome of a contract validation.

    This type does not encode any governance decision (pass/warn/fail). It only
    reports whether the validated artifact is structurally well-formed (``ok``),
    along with any ``errors`` that make it invalid and ``warnings`` that are
    tolerated. Identity fields (``source``, ``schema_version``, ``run_id``) and
    ``events_count`` are optional context populated when available.
    """

    model_config = ConfigDict(extra="forbid")

    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: str | None = None
    schema_version: str | None = None
    run_id: str | None = None
    events_count: int | None = None
