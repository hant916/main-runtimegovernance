"""Regression coverage for preserving existing artifact references."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from ailuros.execution_report import build_run_report, render_run_report_json
from ailuros.projection import build_execution_projection


def _event(
    event_type: str,
    *,
    event_id: str,
    metadata: dict | None = None,
    payload: dict | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": datetime(2026, 9, 1, tzinfo=UTC),
        "payload": payload or {},
        "metadata": metadata or {},
    }


def test_existing_artifact_reference_survives_projection_and_report_export() -> None:
    projection = build_execution_projection(
        "run-artifact-ref",
        "source-a",
        [
            _event(
                "run_started",
                event_id="start",
                metadata={
                    "artifact": "upstream/test.log",
                    "pointer": "runs/run-artifact-ref/tests/1",
                },
            ),
            _event("run_completed", event_id="complete"),
        ],
    )

    assert projection.evidence_refs[0].model_dump() == {
        "event_id": "start",
        "artifact": "upstream/test.log",
        "pointer": "runs/run-artifact-ref/tests/1",
    }

    exported = json.loads(render_run_report_json(build_run_report(projection, [])))
    assert exported["evidence_refs"][0] == {
        "event_id": "start",
        "artifact": "upstream/test.log",
        "pointer": "runs/run-artifact-ref/tests/1",
    }


def test_reference_absence_stays_absent_without_artifact_ownership(tmp_path) -> None:
    missing_artifact = tmp_path / "not-created.log"
    projection = build_execution_projection(
        "run-no-artifact-ref",
        "source-a",
        [_event("run_started", event_id="start")],
    )

    assert projection.evidence_refs[0].artifact is None
    assert projection.evidence_refs[0].pointer is None
    assert not missing_artifact.exists()


def test_external_evidence_metadata_reference_survives_normalization() -> None:
    projection = build_execution_projection(
        "run-external-artifact-ref",
        "source-b",
        [
            {
                "event_id": "external-start",
                "event_type": "external_evidence",
                "timestamp": datetime(2026, 9, 1, tzinfo=UTC),
                "payload": {
                    "event_type": "run_started",
                    "payload": {},
                    "metadata": {
                        "artifact": "producer/run.json",
                        "pointer": "evidence/0",
                    },
                },
            }
        ],
    )

    assert projection.evidence_refs[0].model_dump() == {
        "event_id": "external-start",
        "artifact": "producer/run.json",
        "pointer": "evidence/0",
    }


def test_governance_record_keeps_existing_artifact_reference() -> None:
    projection = build_execution_projection(
        "run-approval-artifact-ref",
        "source-a",
        [
            _event(
                "approval_evidence",
                event_id="approval",
                payload={"subject": "deploy", "decision": "approved"},
                metadata={"artifact": "upstream/approval.json", "pointer": "approval"},
            )
        ],
    )

    assert projection.approval_records[0].evidence_refs[0].model_dump() == {
        "event_id": "approval",
        "artifact": "upstream/approval.json",
        "pointer": "approval",
    }
