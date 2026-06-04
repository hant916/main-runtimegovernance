from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ailuros import EvidenceRecord


class TestEvidenceRecordContract:
    def test_creates_valid_record_with_required_envelope(self) -> None:
        record = EvidenceRecord(
            version="1.0.0",
            run_id="run-test-001",
            event_type="navigation",
            payload={"url": "https://example.com"},
            timestamp=datetime.now(tz=UTC),
        )
        assert record.version == "1.0.0"
        assert record.run_id == "run-test-001"
        assert record.event_type == "navigation"
        assert isinstance(record.timestamp, datetime)
        assert record.timestamp.tzinfo is not None

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

    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord(
                version="1.0.0",
                run_id="run-1",
                event_type="test",
                timestamp=datetime.now(),
            )

    def test_preserves_arbitrary_payload_keys(self) -> None:
        payload = {
            "url": "https://example.com",
            "nested": {"deep": True, "count": 42},
            "items": [1, 2, 3],
        }
        record = EvidenceRecord(
            version="1.0.0",
            run_id="run-test",
            event_type="test",
            payload=payload,
            timestamp=datetime.now(tz=UTC),
        )
        assert record.payload == payload

    def test_payload_defaults_to_empty_dict(self) -> None:
        record = EvidenceRecord(
            version="1.0.0",
            run_id="run-test",
            event_type="test",
            timestamp=datetime.now(tz=UTC),
        )
        assert record.payload == {}

    def test_no_domain_specific_required_fields(self) -> None:
        fields = set(EvidenceRecord.model_fields.keys())
        for forbidden in (
            "browser", "dom", "sidepanel", "cta",
            "supplier", "kyb", "radarCreation",
        ):
            assert forbidden not in fields, f"{forbidden} must not be a field"

    def test_event_type_is_application_neutral_string(self) -> None:
        record = EvidenceRecord(
            version="1.0.0",
            run_id="run-test",
            event_type="custom_domain_event_v2",
            timestamp=datetime.now(tz=UTC),
        )
        assert record.event_type == "custom_domain_event_v2"

    def test_roundtrip_serialization(self) -> None:
        record = EvidenceRecord(
            version="1.0.0",
            run_id="run-test",
            event_type="test",
            payload={"key": "value"},
            timestamp=datetime.now(tz=UTC),
        )
        raw = record.model_dump_json()
        restored = EvidenceRecord.model_validate_json(raw)
        assert restored.version == record.version
        assert restored.run_id == record.run_id
        assert restored.event_type == record.event_type
        assert restored.payload == record.payload

    def test_rejects_unknown_top_level_field(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecord(
                version="1.0.0",
                run_id="run-1",
                event_type="test",
                timestamp=datetime.now(tz=UTC),
                unknown_field="should_fail",
            )
