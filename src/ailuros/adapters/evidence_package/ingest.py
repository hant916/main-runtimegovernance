from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from ailuros._compat import StrEnum
from ailuros.core.evidence import EvidenceEvent as PackageEvent
from ailuros.core.evidence import EvidencePackage
from ailuros.errors import AilurosNotFoundError
from ailuros.models import Environment, Run, RunStatus, RuntimeEvent, RuntimeEventType
from ailuros.storage.sqlite_storage import SQLiteStorage


class ImportStatus(StrEnum):
    CREATED = "created"
    ALREADY_PRESENT = "already_present"
    CONFLICT = "conflict"


class ImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ImportStatus
    run_id: str
    events_imported: int = 0
    events_skipped: int = 0
    source_digest: str | None = None


def _event_content_hash(event: PackageEvent) -> str:
    payload = {
        "event_type": event.event_type,
        "timestamp": event.timestamp.isoformat(),
        "payload": event.payload,
        "metadata": event.metadata,
    }
    raw = str(sorted(payload.items()))
    return hashlib.sha256(raw.encode()).hexdigest()


def _package_to_run(package: EvidencePackage) -> Run:
    now = datetime.now(UTC)
    return Run(
        run_id=package.run_id,
        agent_id=package.source,
        environment=Environment.TEST,
        status=RunStatus.COMPLETED,
        metadata={
            "imported_from_package": True,
            "source": package.source,
            "schema_version": package.schema_version,
        },
        created_at=now,
        updated_at=now,
    )


def _ensure_run(storage: SQLiteStorage, run: Run) -> bool:
    try:
        storage.get_run(run.run_id)
        return False
    except AilurosNotFoundError:
        storage.create_run(run)
        return True


def _package_event_to_runtime(
    event: PackageEvent,
    run_id: str,
    step_id: str | None = None,
) -> RuntimeEvent:
    payload: dict[str, Any] = {
        "event_type": event.event_type,
        "payload": event.payload,
        "metadata": event.metadata,
    }
    scope_ref = event.scope_ref
    if isinstance(scope_ref, str) and scope_ref:
        payload["scope_ref"] = scope_ref
    return RuntimeEvent(
        event_id=event.event_id,
        run_id=run_id,
        step_id=step_id,
        event_type=RuntimeEventType.EXTERNAL_EVIDENCE,
        timestamp=event.timestamp,
        payload=payload,
        scope_ref=scope_ref if isinstance(scope_ref, str) and scope_ref else None,
    )


def _check_event_conflict(
    storage: SQLiteStorage,
    event_id: str,
    content_hash: str,
) -> bool:
    existing = storage.get_event_by_id(event_id)
    if existing is None:
        return False
    existing_payload: dict[str, Any] = existing.payload
    existing_data = {
        "event_type": existing_payload.get("event_type", existing.event_type.value),
        "timestamp": existing.timestamp.isoformat(),
        "payload": existing_payload.get("payload", {}),
        "metadata": existing_payload.get("metadata", {}),
    }
    existing_raw = str(sorted(existing_data.items()))
    existing_hash = hashlib.sha256(existing_raw.encode()).hexdigest()
    return existing_hash != content_hash


def ingest_evidence_package(
    storage: SQLiteStorage,
    package: EvidencePackage,
) -> ImportResult:
    source_digest: str | None = None
    if package.pkg_metadata is not None and package.pkg_metadata.source_digest is not None:
        source_digest = package.pkg_metadata.source_digest

    run = _package_to_run(package)
    run_created = _ensure_run(storage, run)

    events_imported = 0
    events_skipped = 0
    conflict = False

    for event in package.events:
        content_hash = _event_content_hash(event)

        if _check_event_conflict(storage, event.event_id, content_hash):
            conflict = True
            break

        existing = storage.get_event_by_id(event.event_id)
        if existing is not None:
            events_skipped += 1
            continue

        runtime_event = _package_event_to_runtime(event, package.run_id)
        storage.append_event(runtime_event)
        events_imported += 1

    if conflict:
        return ImportResult(
            status=ImportStatus.CONFLICT,
            run_id=package.run_id,
            events_imported=events_imported,
            events_skipped=events_skipped,
            source_digest=source_digest,
        )

    if events_imported == 0 and not run_created:
        return ImportResult(
            status=ImportStatus.ALREADY_PRESENT,
            run_id=package.run_id,
            events_imported=0,
            events_skipped=events_skipped,
            source_digest=source_digest,
        )

    return ImportResult(
        status=ImportStatus.CREATED,
        run_id=package.run_id,
        events_imported=events_imported,
        events_skipped=events_skipped,
        source_digest=source_digest,
    )
