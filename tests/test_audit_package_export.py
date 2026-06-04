from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ailuros import EvidenceRecord
from ailuros.audit.package_export import export_audit_package, export_audit_package_json
from ailuros.evidence.ingest import ingest_evidence
from ailuros.models import Environment, Run, RunStatus, RuntimeEvent, RuntimeEventType
from ailuros.runtime.ids import new_event_id
from ailuros.storage import SQLiteStorage


def _make_run(storage: SQLiteStorage, run_id: str) -> Run:
    now = datetime.now(UTC)
    run = Run(
        run_id=run_id,
        agent_id="agent-1",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        input={"prompt": "test"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    return run


def _make_event(
    run_id: str,
    event_type: RuntimeEventType,
    payload: dict | None = None,
    event_id: str | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id or new_event_id(),
        run_id=run_id,
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload or {},
    )


def _make_evidence_record(**kwargs) -> EvidenceRecord:
    base: dict = {
        "version": "1.0.0",
        "run_id": kwargs.get("run_id", "run-pkg-001"),
        "event_type": "navigation",
        "payload": {"url": "https://example.com", "title": "Test"},
        "timestamp": datetime.now(tz=UTC),
    }
    base.update(kwargs)
    return EvidenceRecord(**base)


class TestAuditPackageSections:
    def test_package_has_all_required_top_level_keys(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-001")

        package = export_audit_package(storage, "run-pkg-001")

        required_keys = {
            "audit_package_version",
            "run_id",
            "generated_at",
            "run",
            "summary",
            "timeline",
            "decisions",
            "evidence",
            "validation",
            "replay",
        }
        assert set(package.keys()) == required_keys

    def test_package_version_is_one(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-001")

        package = export_audit_package(storage, "run-pkg-001")
        assert package["audit_package_version"] == "1"

    def test_package_run_section_has_metadata(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-001")

        package = export_audit_package(storage, "run-pkg-001")
        assert package["run"]["agent_id"] == "agent-1"
        assert package["run"]["environment"] == "development"
        assert package["run"]["status"] == "running"

    def test_package_summary_section_has_expected_fields(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-001")

        package = export_audit_package(storage, "run-pkg-001")
        summary = package["summary"]
        assert "decision" in summary
        assert "reason" in summary
        assert "tool" in summary
        assert "path_validation" in summary
        assert "event_count" in summary
        assert "decision_counts" in summary
        assert "blocked_count" in summary
        assert "review_count" in summary

    def test_package_validation_section_has_path_validations_key(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-001")

        package = export_audit_package(storage, "run-pkg-001")
        assert "path_validations" in package["validation"]


class TestAuditPackageTimeline:
    def test_timeline_includes_all_events_in_sequence_order(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-002")
        e1 = storage.append_event(_make_event("run-pkg-002", RuntimeEventType.RUN_STARTED))
        e2 = storage.append_event(_make_event("run-pkg-002", RuntimeEventType.USER_INPUT_RECEIVED))
        e3 = storage.append_event(_make_event("run-pkg-002", RuntimeEventType.RUN_COMPLETED))

        package = export_audit_package(storage, "run-pkg-002")

        assert len(package["timeline"]) == 3
        assert package["timeline"][0]["event_id"] == e1.event_id
        assert package["timeline"][1]["event_id"] == e2.event_id
        assert package["timeline"][2]["event_id"] == e3.event_id

    def test_timeline_entries_have_required_fields(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-003")
        storage.append_event(_make_event("run-pkg-003", RuntimeEventType.RUN_STARTED))

        package = export_audit_package(storage, "run-pkg-003")
        entry = package["timeline"][0]

        assert "event_id" in entry
        assert "event_type" in entry
        assert "timestamp" in entry


class TestAuditPackageDecisions:
    def test_decisions_extracted_from_governance_decision_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-004")
        storage.append_event(_make_event("run-pkg-004", RuntimeEventType.RUN_STARTED))
        storage.append_event(_make_event("run-pkg-004", RuntimeEventType.GOVERNANCE_DECISION, {
            "decision": "allow",
            "reason": "ok",
            "tool_name": "bash",
            "allowed": True,
        }))
        storage.append_event(_make_event("run-pkg-004", RuntimeEventType.RUN_COMPLETED))

        package = export_audit_package(storage, "run-pkg-004")

        assert len(package["decisions"]) == 1
        decision = package["decisions"][0]
        assert decision["decision"] == "allow"
        assert decision["reason"] == "ok"
        assert decision["tool_name"] == "bash"

    def test_decisions_empty_when_no_governance_decision_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-005")
        storage.append_event(_make_event("run-pkg-005", RuntimeEventType.RUN_STARTED))
        storage.append_event(_make_event("run-pkg-005", RuntimeEventType.RUN_COMPLETED))

        package = export_audit_package(storage, "run-pkg-005")
        assert package["decisions"] == []

    def test_decisions_sorted_by_sequence(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-006")
        storage.append_event(_make_event("run-pkg-006", RuntimeEventType.GOVERNANCE_DECISION, {
            "decision": "warn",
        }))
        storage.append_event(_make_event("run-pkg-006", RuntimeEventType.GOVERNANCE_DECISION, {
            "decision": "block",
        }))

        package = export_audit_package(storage, "run-pkg-006")
        assert package["decisions"][0]["decision"] == "warn"
        assert package["decisions"][1]["decision"] == "block"


class TestAuditPackageEvidence:
    def test_evidence_matches_export_evidence(self, tmp_path: Path) -> None:
        from ailuros.evidence.export import export_evidence

        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-007")
        record = _make_evidence_record(run_id="run-pkg-007")
        ingest_evidence(storage, record)

        package = export_audit_package(storage, "run-pkg-007")
        evidence_expected = export_evidence(storage, "run-pkg-007")

        assert package["evidence"] == evidence_expected

    def test_evidence_empty_when_no_evidence_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-008")
        storage.append_event(_make_event("run-pkg-008", RuntimeEventType.RUN_STARTED))

        package = export_audit_package(storage, "run-pkg-008")
        assert package["evidence"] == []


class TestAuditPackageValidation:
    def test_validation_includes_path_validation_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-009")
        storage.append_event(_make_event("run-pkg-009", RuntimeEventType.PATH_VALIDATION_RESULT, {
            "valid": True,
            "path_id": "paths/allow.txt",
        }))

        package = export_audit_package(storage, "run-pkg-009")
        validations = package["validation"]["path_validations"]
        assert len(validations) == 1
        assert validations[0]["valid"] is True
        assert validations[0]["path_id"] == "paths/allow.txt"

    def test_validation_empty_when_no_path_validation_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-010")
        storage.append_event(_make_event("run-pkg-010", RuntimeEventType.RUN_STARTED))

        package = export_audit_package(storage, "run-pkg-010")
        assert package["validation"]["path_validations"] == []


class TestAuditPackageReplay:
    def test_replay_none_when_no_replay_runs(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-011")

        package = export_audit_package(storage, "run-pkg-011")
        assert package["replay"] is None

    def test_replay_includes_saved_replay_result(self, tmp_path: Path) -> None:
        from ailuros.models import ReplayResult

        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-012")
        storage.save_replay_result(ReplayResult(
            replay_id="replay-1",
            run_id="run-pkg-012",
            status="completed",
            key_events=[{"seq": 1, "type": "run_started"}],
            metadata={"source": "test"},
            created_at=datetime.now(UTC),
        ))

        package = export_audit_package(storage, "run-pkg-012")
        assert package["replay"] is not None
        assert len(package["replay"]["replay_runs"]) == 1
        assert package["replay"]["replay_runs"][0]["replay_id"] == "replay-1"


class TestAuditPackageDeterminism:
    def test_json_output_is_deterministic(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-013")
        storage.append_event(_make_event("run-pkg-013", RuntimeEventType.RUN_STARTED))
        storage.append_event(_make_event("run-pkg-013", RuntimeEventType.GOVERNANCE_DECISION, {
            "decision": "allow",
            "reason": "safe",
        }))

        pkg1 = json.loads(export_audit_package_json(storage, "run-pkg-013"))
        pkg2 = json.loads(export_audit_package_json(storage, "run-pkg-013"))
        del pkg1["generated_at"]
        del pkg2["generated_at"]
        assert pkg1 == pkg2

    def test_json_sorted_keys_for_nested_objects(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-014")
        storage.append_event(_make_event("run-pkg-014", RuntimeEventType.GOVERNANCE_DECISION, {
            "decision": "allow",
            "reason": "safe",
            "tool_name": "bash",
        }))

        output = export_audit_package_json(storage, "run-pkg-014")
        parsed = json.loads(output)
        decision = parsed["decisions"][0]
        fields = list(decision.keys())
        assert fields == sorted(fields)


class TestAuditPackageReadOnly:
    def test_export_does_not_mutate_storage(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-015")
        storage.append_event(_make_event("run-pkg-015", RuntimeEventType.RUN_STARTED))

        events_before = storage.list_events("run-pkg-015")
        export_audit_package(storage, "run-pkg-015")
        events_after = storage.list_events("run-pkg-015")

        assert len(events_before) == len(events_after)
        assert events_before[0].event_id == events_after[0].event_id

    def test_export_does_not_create_writes(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-016")
        storage.append_event(_make_event("run-pkg-016", RuntimeEventType.RUN_STARTED))

        existing_ids = {r.run_id for r in storage.list_runs()}
        export_audit_package(storage, "run-pkg-016")
        after_ids = {r.run_id for r in storage.list_runs()}

        assert existing_ids == after_ids


class TestAuditPackageNoHiddenChainOfThought:
    def test_package_excludes_raw_runtime_state_fields(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-017")
        storage.append_event(_make_event("run-pkg-017", RuntimeEventType.RUN_STARTED))

        package = export_audit_package(storage, "run-pkg-017")
        hidden_keys = {
            "chain_of_thought", "cot", "model_internals",
            "_internal", "private_state",
        }
        keys = _collect_keys(package)
        assert not (hidden_keys & set(keys))

    def test_package_timeline_excludes_raw_payload(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-018")
        storage.append_event(_make_event("run-pkg-018", RuntimeEventType.RUN_STARTED))

        package = export_audit_package(storage, "run-pkg-018")
        for entry in package["timeline"]:
            assert "payload" not in entry
            assert "payload_json" not in entry


class TestAuditPackageErrorHandling:
    def test_raises_not_found_for_unknown_run(self, tmp_path: Path) -> None:
        from ailuros.errors import AilurosNotFoundError

        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()

        with pytest.raises(AilurosNotFoundError):
            export_audit_package(storage, "nonexistent-run")

    def test_partial_run_with_no_events_is_valid(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-019")

        package = export_audit_package(storage, "run-pkg-019")
        assert package["timeline"] == []
        assert package["decisions"] == []
        assert package["evidence"] == []
        assert package["summary"]["event_count"] == 0


class TestAuditPackageJSONExport:
    def test_json_output_is_valid_json(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-020")
        storage.append_event(_make_event("run-pkg-020", RuntimeEventType.RUN_STARTED))
        storage.append_event(_make_event("run-pkg-020", RuntimeEventType.GOVERNANCE_DECISION, {
            "decision": "allow",
            "reason": "safe",
        }))

        output = export_audit_package_json(storage, "run-pkg-020")
        parsed = json.loads(output)
        assert parsed["run_id"] == "run-pkg-020"
        assert len(parsed["timeline"]) == 2
        assert len(parsed["decisions"]) == 1

    def test_json_output_with_evidence_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-pkg-021")
        record = _make_evidence_record(run_id="run-pkg-021")
        ingest_evidence(storage, record)

        output = export_audit_package_json(storage, "run-pkg-021")
        parsed = json.loads(output)
        assert len(parsed["evidence"]) == 1
        assert parsed["evidence"][0]["event_id"].startswith("evt_")


def _collect_keys(obj: object, prefix: str = "") -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.append(k)
            keys.extend(_collect_keys(v, f"{prefix}.{k}"))
    elif isinstance(obj, list):
        for item in obj:
            keys.extend(_collect_keys(item, prefix))
    return keys
