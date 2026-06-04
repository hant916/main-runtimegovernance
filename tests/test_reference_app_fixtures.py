from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ailuros import EvidenceRecord

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "examples" / "reference_apps" / "fixtures"

FIXTURE_FILES = {
    "clarify_browser": FIXTURES_DIR / "clarify_browser.json",
    "everrun_execution": FIXTURES_DIR / "everrun_execution.json",
    "radarcreation_risk": FIXTURES_DIR / "radarcreation_risk.json",
}


def _load_fixture(name: str) -> dict:
    path = FIXTURE_FILES.get(name)
    if path is None or not path.is_file():
        pytest.skip(f"Fixture not found: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


class TestReferenceAppFixturesExist:
    def test_clarify_fixture_present(self) -> None:
        assert FIXTURE_FILES["clarify_browser"].is_file()

    def test_everrun_fixture_present(self) -> None:
        assert FIXTURE_FILES["everrun_execution"].is_file()

    def test_radarcreation_fixture_present(self) -> None:
        assert FIXTURE_FILES["radarcreation_risk"].is_file()


class TestReferenceAppFixturesAreValidEvidenceRecords:
    def test_clarify_validates_against_evidence_contract(self) -> None:
        raw = _load_fixture("clarify_browser")
        record = EvidenceRecord(**raw)
        assert isinstance(record, EvidenceRecord)

    def test_everrun_validates_against_evidence_contract(self) -> None:
        raw = _load_fixture("everrun_execution")
        record = EvidenceRecord(**raw)
        assert isinstance(record, EvidenceRecord)

    def test_radarcreation_validates_against_evidence_contract(self) -> None:
        raw = _load_fixture("radarcreation_risk")
        record = EvidenceRecord(**raw)
        assert isinstance(record, EvidenceRecord)


class TestReferenceAppFixturesRequiredFields:
    def test_clarify_has_required_fields(self) -> None:
        raw = _load_fixture("clarify_browser")
        record = EvidenceRecord(**raw)
        assert record.version == raw["version"]
        assert record.run_id == raw["run_id"]
        assert record.event_type == raw["event_type"]
        assert isinstance(record.timestamp, datetime)
        assert record.timestamp.tzinfo is not None

    def test_everrun_has_required_fields(self) -> None:
        raw = _load_fixture("everrun_execution")
        record = EvidenceRecord(**raw)
        assert record.version == raw["version"]
        assert record.run_id == raw["run_id"]
        assert record.event_type == raw["event_type"]
        assert isinstance(record.timestamp, datetime)
        assert record.timestamp.tzinfo is not None

    def test_radarcreation_has_required_fields(self) -> None:
        raw = _load_fixture("radarcreation_risk")
        record = EvidenceRecord(**raw)
        assert record.version == raw["version"]
        assert record.run_id == raw["run_id"]
        assert record.event_type == raw["event_type"]
        assert isinstance(record.timestamp, datetime)
        assert record.timestamp.tzinfo is not None


class TestReferenceAppFixturesPayloadOpaque:
    def test_clarify_payload_preserved_as_is(self) -> None:
        raw = _load_fixture("clarify_browser")
        record = EvidenceRecord(**raw)
        assert record.payload == raw["payload"]

    def test_everrun_payload_preserved_as_is(self) -> None:
        raw = _load_fixture("everrun_execution")
        record = EvidenceRecord(**raw)
        assert record.payload == raw["payload"]

    def test_radarcreation_payload_preserved_as_is(self) -> None:
        raw = _load_fixture("radarcreation_risk")
        record = EvidenceRecord(**raw)
        assert record.payload == raw["payload"]

    def test_core_does_not_validate_payload_schema(self) -> None:
        raw = _load_fixture("radarcreation_risk")
        record = EvidenceRecord(**raw)
        assert "scores" in record.payload
        assert record.payload["scores"]["confidentiality"] == 0.1


class TestReferenceAppFixturesRoundTrip:
    def test_clarify_serializes_and_restores(self) -> None:
        raw = _load_fixture("clarify_browser")
        original = EvidenceRecord(**raw)
        restored = EvidenceRecord.model_validate_json(original.model_dump_json())
        assert restored.version == original.version
        assert restored.run_id == original.run_id
        assert restored.event_type == original.event_type
        assert restored.payload == original.payload

    def test_everrun_serializes_and_restores(self) -> None:
        raw = _load_fixture("everrun_execution")
        original = EvidenceRecord(**raw)
        restored = EvidenceRecord.model_validate_json(original.model_dump_json())
        assert restored.version == original.version
        assert restored.run_id == original.run_id
        assert restored.event_type == original.event_type
        assert restored.payload == original.payload

    def test_radarcreation_serializes_and_restores(self) -> None:
        raw = _load_fixture("radarcreation_risk")
        original = EvidenceRecord(**raw)
        restored = EvidenceRecord.model_validate_json(original.model_dump_json())
        assert restored.version == original.version
        assert restored.run_id == original.run_id
        assert restored.event_type == original.event_type
        assert restored.payload == original.payload


class TestReferenceAppFixturesNoExtraFields:
    def test_clarify_rejects_unknown_top_level_field(self) -> None:
        raw = _load_fixture("clarify_browser")
        raw["not_a_field"] = "should_fail"
        with pytest.raises(ValidationError):
            EvidenceRecord(**raw)

    def test_everrun_rejects_unknown_top_level_field(self) -> None:
        raw = _load_fixture("everrun_execution")
        raw["unknown_prop"] = 42
        with pytest.raises(ValidationError):
            EvidenceRecord(**raw)

    def test_radarcreation_rejects_unknown_top_level_field(self) -> None:
        raw = _load_fixture("radarcreation_risk")
        raw["extra"] = True
        with pytest.raises(ValidationError):
            EvidenceRecord(**raw)


class TestReferenceAppFixturesFreeFormEventType:
    def test_clarify_event_type_is_free_form(self) -> None:
        raw = _load_fixture("clarify_browser")
        record = EvidenceRecord(**raw)
        assert record.event_type == "clarify.browser.navigation"

    def test_everrun_event_type_is_free_form(self) -> None:
        raw = _load_fixture("everrun_execution")
        record = EvidenceRecord(**raw)
        assert record.event_type == "everrun.execution.tool_call"

    def test_radarcreation_event_type_is_free_form(self) -> None:
        raw = _load_fixture("radarcreation_risk")
        record = EvidenceRecord(**raw)
        assert record.event_type == "radarCreation.risk.assessment"
