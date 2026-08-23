from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_artifact: str | None = None
    source_pointer: str | None = None
    source_event_type: str | None = None
    metadata: dict[str, Any] = {}


class PackageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exporter_version: str | None = None
    source_digest: str | None = None
    coverage: dict[str, Any] | None = None

    @field_validator("exporter_version")
    @classmethod
    def validate_exporter_version(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("exporter_version must not be empty if present")
        return value


class EvidenceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    timestamp: datetime
    payload: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    scope_ref: str | None = None

    @field_validator("scope_ref", mode="before")
    @classmethod
    def require_scope_ref_string(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise ValueError("scope_ref must be a string or None")

    @field_validator("event_id")
    @classmethod
    def require_non_empty_event_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("event_id must not be empty")
        return value

    @field_validator("event_type")
    @classmethod
    def require_non_empty_event_type(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("event_type must not be empty")
        return value

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class EvidencePackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    schema_version: str
    run_id: str
    events: list[EvidenceEvent] = []
    files: dict[str, str] = {}
    metadata: dict[str, Any] = {}
    provenance: Provenance | None = None
    pkg_metadata: PackageMetadata | None = None
