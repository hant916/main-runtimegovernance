from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ailuros import EvidenceRecord


def _valid_record(**kwargs) -> EvidenceRecord:
    base: dict = {
        "version": "1.0.0",
        "run_id": "run-test-001",
        "event_type": "navigation",
        "payload": {"url": "https://example.com", "title": "Test Page"},
        "timestamp": datetime.now(tz=UTC),
    }
    base.update(kwargs)
    return EvidenceRecord(**base)


class TestValidEvidenceRecord:
    def test_creates_with_required_fields(self) -> None:
        record = _valid_record()
        assert record.version == "1.0.0"
        assert record.run_id == "run-test-001"
        assert record.event_type == "navigation"
        assert isinstance(record.timestamp, datetime)

    def test_serializes_to_json(self) -> None:
        record = _valid_record()
        dumped = record.model_dump_json()
        assert "run-test-001" in dumped
        assert "navigation" in dumped

    def test_round_trips_through_json(self) -> None:
        record = _valid_record()
        raw = record.model_dump_json()
        restored = EvidenceRecord.model_validate_json(raw)
        assert restored.version == record.version
        assert restored.run_id == record.run_id
        assert restored.event_type == record.event_type
        assert restored.payload == record.payload

    def test_payload_defaults_to_empty_dict(self) -> None:
        record = EvidenceRecord(
            version="1.0.0",
            run_id="run-test-002",
            event_type="interaction",
            timestamp=datetime.now(tz=UTC),
        )
        assert record.payload == {}


class TestPayloadPreservation:
    def test_preserves_arbitrary_payload_keys(self) -> None:
        payload = {
            "url": "https://example.com",
            "title": "My Page",
            "nested": {"deep": True, "count": 42},
            "items": [1, 2, 3],
        }
        record = _valid_record(payload=payload)
        assert record.payload == payload

    def test_preserves_minimal_payload(self) -> None:
        record = _valid_record(payload={"key": "value"})
        assert record.payload == {"key": "value"}

    def test_preserves_empty_payload(self) -> None:
        record = _valid_record(payload={})
        assert record.payload == {}

    def test_does_not_validate_payload_internals(self) -> None:
        record = _valid_record(payload={"anything": "goes", "domain": "unknown"})
        assert record.payload["anything"] == "goes"
        assert record.payload["domain"] == "unknown"


class TestRejectsExtraFields:
    def test_rejects_unknown_top_level_field(self) -> None:
        with pytest.raises(ValidationError):
            _valid_record(unknown_field="should_fail")


class TestTimestampValidation:
    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValidationError):
            _valid_record(timestamp=datetime.now())

    def test_accepts_timezone_aware_datetime(self) -> None:
        record = _valid_record(timestamp=datetime.now(tz=UTC))
        assert record.timestamp.tzinfo is not None


class TestRequiredFields:
    def test_rejects_missing_version(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord(
                run_id="run-1",
                event_type="test",
                timestamp=datetime.now(tz=UTC),
            )

    def test_rejects_missing_run_id(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord(
                version="1.0.0",
                event_type="test",
                timestamp=datetime.now(tz=UTC),
            )

    def test_rejects_missing_event_type(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord(
                version="1.0.0",
                run_id="run-1",
                timestamp=datetime.now(tz=UTC),
            )

    def test_rejects_missing_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord(
                version="1.0.0",
                run_id="run-1",
                event_type="test",
            )


class TestApplicationNeutral:
    def test_event_type_is_free_form_string(self) -> None:
        record = _valid_record(event_type="custom_domain_event_v2")
        assert record.event_type == "custom_domain_event_v2"

    def test_no_clarify_specific_fields(self) -> None:
        fields = set(EvidenceRecord.model_fields.keys())
        assert "browser" not in fields
        assert "dom" not in fields
        assert "sidepanel" not in fields
        assert "cta" not in fields
        assert "supplier" not in fields
        assert "kyb" not in fields
        assert "radarCreation" not in fields

    def test_event_type_not_restricted_to_runtime_enum(self) -> None:
        record = _valid_record(event_type="external_evidence_event")
        dumped = record.model_dump(mode="json")
        assert dumped["event_type"] == "external_evidence_event"
