from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from ailuros.adapters.evidence_package import load_evidence_package
from ailuros.core.evidence import (
    EvidenceEvent,
    EvidencePackage,
    PackageMetadata,
    Provenance,
)

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "evidence_package"
VALID_PKG = FIXTURES / "valid-v15"


class TestBackwardsCompatibility:
    def test_valid_v15_fixture_still_loads(self) -> None:
        pkg = load_evidence_package(VALID_PKG)
        assert pkg.source == "sample-agent"
        assert pkg.schema_version == "ailuros.timeline.v0"
        assert pkg.run_id == "run-sample-001"
        assert len(pkg.events) == 2
        assert pkg.provenance is None
        assert pkg.pkg_metadata is None

    def test_valid_v15_events_have_timezone(self) -> None:
        pkg = load_evidence_package(VALID_PKG)
        for ev in pkg.events:
            assert ev.timestamp.tzinfo is not None

    def test_valid_v15_events_have_non_empty_identity(self) -> None:
        pkg = load_evidence_package(VALID_PKG)
        for ev in pkg.events:
            assert ev.event_id.strip()
            assert ev.event_type.strip()

    def test_package_loads_without_provenance_fields(self) -> None:
        pkg = load_evidence_package(VALID_PKG)
        dumped = pkg.model_dump(mode="json")
        assert "provenance" in dumped
        assert dumped["provenance"] is None
        assert "pkg_metadata" in dumped
        assert dumped["pkg_metadata"] is None


class TestProvenance:
    def test_provenance_defaults(self) -> None:
        prov = Provenance()
        assert prov.source_artifact is None
        assert prov.source_pointer is None
        assert prov.source_event_type is None
        assert prov.metadata == {}

    def test_provenance_with_values(self) -> None:
        prov = Provenance(
            source_artifact="agent-foo-v1",
            source_pointer="run-123/step-456",
            source_event_type="tool_call_requested",
            metadata={"framework": "langchain"},
        )
        assert prov.source_artifact == "agent-foo-v1"
        assert prov.source_pointer == "run-123/step-456"
        assert prov.source_event_type == "tool_call_requested"
        assert prov.metadata == {"framework": "langchain"}

    def test_provenance_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            Provenance(source_artifact="x", planner="should_not_be_here")  # type: ignore[call-arg]

    def test_provenance_round_trips_through_json(self) -> None:
        prov = Provenance(
            source_artifact="agent-v2",
            source_event_type="run_started",
            metadata={"key": "val"},
        )
        raw = prov.model_dump_json()
        restored = Provenance.model_validate_json(raw)
        assert restored.source_artifact == "agent-v2"
        assert restored.source_event_type == "run_started"
        assert restored.metadata == {"key": "val"}

    def test_package_with_provenance(self) -> None:
        prov = Provenance(
            source_artifact="exporter-v1",
            source_pointer="pipeline/run-42",
        )
        pkg = EvidencePackage(
            source="test",
            schema_version="v1",
            run_id="r1",
            provenance=prov,
        )
        assert pkg.provenance is not None
        assert pkg.provenance.source_artifact == "exporter-v1"
        assert pkg.provenance.source_pointer == "pipeline/run-42"


class TestPackageMetadata:
    def test_pkg_metadata_defaults(self) -> None:
        meta = PackageMetadata()
        assert meta.exporter_version is None
        assert meta.source_digest is None
        assert meta.coverage is None

    def test_pkg_metadata_with_values(self) -> None:
        meta = PackageMetadata(
            exporter_version="3.2.1",
            source_digest="sha256:abc123",
            coverage={"events": 42, "files": 3},
        )
        assert meta.exporter_version == "3.2.1"
        assert meta.source_digest == "sha256:abc123"
        assert meta.coverage == {"events": 42, "files": 3}

    def test_pkg_metadata_validates_exporter_version_not_empty(self) -> None:
        with pytest.raises(ValidationError):
            PackageMetadata(exporter_version="   ")

    def test_pkg_metadata_allows_none_exporter_version(self) -> None:
        meta = PackageMetadata(exporter_version=None)
        assert meta.exporter_version is None

    def test_pkg_metadata_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            PackageMetadata(exporter_version="1", unknown="bad")  # type: ignore[call-arg]

    def test_pkg_metadata_round_trips_through_json(self) -> None:
        meta = PackageMetadata(
            exporter_version="2.0.0",
            source_digest="sha256:def456",
            coverage={"total": 10},
        )
        raw = meta.model_dump_json()
        restored = PackageMetadata.model_validate_json(raw)
        assert restored.exporter_version == "2.0.0"
        assert restored.source_digest == "sha256:def456"
        assert restored.coverage == {"total": 10}

    def test_pkg_metadata_in_package(self) -> None:
        meta = PackageMetadata(exporter_version="4.0.0", source_digest="sha256:fff")
        pkg = EvidencePackage(
            source="test",
            schema_version="v1",
            run_id="r1",
            pkg_metadata=meta,
        )
        assert pkg.pkg_metadata is not None
        assert pkg.pkg_metadata.exporter_version == "4.0.0"
        assert pkg.pkg_metadata.source_digest == "sha256:fff"


class TestEvidenceEventIdentityValidation:
    def test_rejects_empty_event_id(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceEvent(
                event_id="",
                event_type="run_started",
                timestamp=datetime.now(tz=UTC),
            )

    def test_rejects_whitespace_event_id(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceEvent(
                event_id="   ",
                event_type="run_started",
                timestamp=datetime.now(tz=UTC),
            )

    def test_rejects_empty_event_type(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceEvent(
                event_id="evt-1",
                event_type="",
                timestamp=datetime.now(tz=UTC),
            )

    def test_rejects_whitespace_event_type(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceEvent(
                event_id="evt-1",
                event_type="   ",
                timestamp=datetime.now(tz=UTC),
            )

    def test_accepts_non_empty_event_id(self) -> None:
        ev = EvidenceEvent(
            event_id="evt-001",
            event_type="run_started",
            timestamp=datetime.now(tz=UTC),
        )
        assert ev.event_id == "evt-001"

    def test_accepts_non_empty_event_type(self) -> None:
        ev = EvidenceEvent(
            event_id="evt-001",
            event_type="custom_event",
            timestamp=datetime.now(tz=UTC),
        )
        assert ev.event_type == "custom_event"


class TestTimestampValidation:
    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceEvent(
                event_id="evt-1",
                event_type="run_started",
                timestamp=datetime.now(),
            )

    def test_accepts_utc_datetime(self) -> None:
        ev = EvidenceEvent(
            event_id="evt-1",
            event_type="run_started",
            timestamp=datetime.now(tz=UTC),
        )
        assert ev.timestamp.tzinfo is not None

    def test_accepts_offset_datetime(self) -> None:
        tz = timezone(timedelta(hours=5, minutes=30))
        ev = EvidenceEvent(
            event_id="evt-1",
            event_type="run_started",
            timestamp=datetime.now(tz=tz),
        )
        assert ev.timestamp.tzinfo is not None


class TestUnknownEventTypeAllowed:
    def test_accepts_arbitrary_event_type_string(self) -> None:
        ev = EvidenceEvent(
            event_id="evt-1",
            event_type="custom_domain_specific_event_v99",
            timestamp=datetime.now(tz=UTC),
        )
        assert ev.event_type == "custom_domain_specific_event_v99"

    def test_accepts_external_event_type(self) -> None:
        ev = EvidenceEvent(
            event_id="evt-1",
            event_type="external_system_notification",
            timestamp=datetime.now(tz=UTC),
        )
        assert ev.event_type == "external_system_notification"

    def test_event_type_not_restricted_to_enum(self) -> None:
        fields = EvidenceEvent.model_fields
        assert fields["event_type"].annotation in (str, "str")
        # No enum constraint; any string is valid as long as non-empty
        ev = EvidenceEvent(
            event_id="evt-1",
            event_type="any_string_here",
            timestamp=datetime.now(tz=UTC),
        )
        raw = ev.model_dump(mode="json")
        assert raw["event_type"] == "any_string_here"


class TestEvidencePackageRoundTrip:
    def test_package_with_all_new_fields_round_trips(self) -> None:
        prov = Provenance(
            source_artifact="agent-v1",
            source_pointer="run/r1",
            source_event_type="run_started",
            metadata={"env": "prod"},
        )
        meta = PackageMetadata(
            exporter_version="1.2.3",
            source_digest="sha256:abc",
            coverage={"total": 10},
        )
        ev = EvidenceEvent(
            event_id="evt-1",
            event_type="custom_event",
            timestamp=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )
        pkg = EvidencePackage(
            source="test-source",
            schema_version="ailuros.timeline.v1",
            run_id="run-001",
            events=[ev],
            files={"manifest.json": "manifest.json"},
            metadata={"agent_name": "test"},
            provenance=prov,
            pkg_metadata=meta,
        )

        raw = pkg.model_dump_json()
        restored = EvidencePackage.model_validate_json(raw)
        assert restored.source == "test-source"
        assert restored.events[0].event_id == "evt-1"
        assert restored.provenance is not None
        assert restored.provenance.source_artifact == "agent-v1"
        assert restored.pkg_metadata is not None
        assert restored.pkg_metadata.exporter_version == "1.2.3"
