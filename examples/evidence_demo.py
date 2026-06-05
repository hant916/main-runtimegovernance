from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ailuros.evaluation import (
    EvaluationCase,
    EvaluationService,
    EvidenceEventExpectation,
)
from ailuros.evidence import EvidenceRecord, export_evidence, ingest_evidence
from ailuros.models import Environment, Run, RunStatus
from ailuros.regression import RegressionService
from ailuros.storage import SQLiteStorage

RUN_ID = "demo-evidence-run"
AGENT_ID = "demo-agent"
FIXTURE_PATH = Path(__file__).resolve().parent / "reference_apps" / "evidence_local_fixture.json"


def _make_run(storage: SQLiteStorage) -> None:
    now = datetime.now(UTC)
    run = Run(
        run_id=RUN_ID,
        agent_id=AGENT_ID,
        environment=Environment.DEVELOPMENT,
        status=RunStatus.COMPLETED,
        input={"prompt": "evidence pipeline demo"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)


def _make_record(event_type: str, payload: dict, ts: datetime) -> EvidenceRecord:
    return EvidenceRecord(
        version="1.0.0",
        run_id=RUN_ID,
        event_type=event_type,
        payload=payload,
        timestamp=ts,
    )


def run_demo() -> dict:
    tmp_dir = Path(tempfile.mkdtemp())
    storage = SQLiteStorage(tmp_dir / "evidence_demo.sqlite")
    storage.init()
    _make_run(storage)

    base_ts = datetime(2026, 6, 5, 0, 0, 0, tzinfo=UTC)

    records = [
        _make_record(
            "scan_result",
            {"target": "readme.md", "lines_scanned": 42, "findings": 0},
            base_ts,
        ),
        _make_record(
            "transform_result",
            {"source": "input.csv", "rows_transformed": 150, "target_format": "json"},
            datetime(2026, 6, 5, 0, 0, 1, tzinfo=UTC),
        ),
        _make_record(
            "quality_report",
            {"check": "schema_validation", "passed": True, "errors": []},
            datetime(2026, 6, 5, 0, 0, 2, tzinfo=UTC),
        ),
    ]

    for rec in records:
        ingest_evidence(storage, rec)

    exported = export_evidence(storage, RUN_ID)
    assert len(exported) == 3, f"Expected 3 evidence records, got {len(exported)}"

    cases = [
        EvaluationCase(
            id="demo.evidence.scan_present",
            name="Scan result evidence event exists",
            expectations=[
                EvidenceEventExpectation(
                    evidence_event_type="scan_result", version="1.0.0"
                )
            ],
        ),
    ]
    events = storage.list_events(RUN_ID)
    eval_service = EvaluationService()
    eval_results = eval_service.evaluate(events, cases)
    assert eval_results[0].passed, f"Evaluation failed: {eval_results[0].failures}"

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    regression = RegressionService()
    identical_result = regression.compare_evidence_timeline(fixture, exported)
    assert identical_result.passed, (
        f"Regression: {len(identical_result.diffs)} diffs"
    )

    modified = list(exported)
    modified.append(
        {
            "event_id": "demo-evt-extra",
            "run_id": RUN_ID,
            "event_type": "evidence",
            "timestamp": "2026-06-05T00:00:03+00:00",
            "sequence": 4,
            "evidence": {
                "version": "1.0.0",
                "event_type": "extra_event",
                "payload": {"note": "added"},
            },
        }
    )
    diff_result = regression.compare_evidence_timeline(
        exported, modified, payload_paths=["payload.note"]
    )
    assert not diff_result.passed
    assert any(d.kind == "added_evidence" for d in diff_result.diffs)

    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "exported_count": len(exported),
        "evaluation_passed": eval_results[0].passed,
        "regression_passed": identical_result.passed,
        "regression_diff_detected": not diff_result.passed,
    }


def main() -> None:
    result = run_demo()
    print("=== Evidence Pipeline Demo ===")
    print(f"  Evidence records exported: {result['exported_count']}")
    print(f"  Evaluation passed:         {result['evaluation_passed']}")
    print(f"  Regression passed:         {result['regression_passed']}")
    print(f"  Regression diff detected:  {result['regression_diff_detected']}")
    print("Demo complete.")


if __name__ == "__main__":
    main()
