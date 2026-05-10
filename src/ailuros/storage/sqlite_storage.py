from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ailuros.errors import AilurosDataCorruptionError, AilurosNotFoundError, AilurosStorageError
from ailuros.models import (
    AuditReport,
    EvaluationResult,
    GovernanceDecision,
    ReplayResult,
    Run,
    RunStatus,
    RuntimeEvent,
    Step,
    StepStatus,
)


class SQLiteStorage:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            sql = Path(__file__).with_name("migrations").joinpath("001_initial.sql").read_text()
            conn.executescript(sql)
            conn.execute(
                "INSERT OR IGNORE INTO migrations(version, applied_at) VALUES (?, ?)",
                ("001_initial", datetime.now(timezone.utc).isoformat()),
            )

    def create_run(self, run: Run) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.agent_id,
                    run.environment.value,
                    run.status.value,
                    self._dumps(run.input),
                    run.user_id,
                    self._dumps(run.metadata),
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )

    def get_run(self, run_id: str) -> Run:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise AilurosNotFoundError(f"run not found: {run_id}")
        return self._row_to_run(row)

    def list_runs(self) -> list[Run]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [self._row_to_run(row) for row in rows]

    def update_run_status(self, run_id: str, status: RunStatus) -> None:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE run_id = ?",
                (status.value, datetime.now(timezone.utc).isoformat(), run_id),
            )
        if cur.rowcount == 0:
            raise AilurosNotFoundError(f"run not found: {run_id}")

    def create_step(self, step: Step) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO steps VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    step.step_id,
                    step.run_id,
                    step.step_type.value,
                    step.status.value,
                    step.name,
                    self._dumps(step.metadata),
                    step.created_at.isoformat(),
                    step.updated_at.isoformat(),
                ),
            )

    def get_step(self, step_id: str) -> Step:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM steps WHERE step_id = ?", (step_id,)).fetchone()
        if row is None:
            raise AilurosNotFoundError(f"step not found: {step_id}")
        return Step(
            step_id=row["step_id"],
            run_id=row["run_id"],
            step_type=row["step_type"],
            status=row["status"],
            name=row["name"],
            metadata=self._loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def update_step_status(self, step_id: str, status: StepStatus) -> None:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE steps SET status = ?, updated_at = ? WHERE step_id = ?",
                (status.value, datetime.now(timezone.utc).isoformat(), step_id),
            )
        if cur.rowcount == 0:
            raise AilurosNotFoundError(f"step not found: {step_id}")

    def append_event(self, event: RuntimeEvent) -> RuntimeEvent:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM events WHERE run_id = ?",
                (event.run_id,),
            ).fetchone()
            sequence = int(row["next_sequence"])
            stored = event.model_copy(update={"sequence": sequence})
            conn.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    stored.event_id,
                    stored.run_id,
                    stored.step_id,
                    stored.event_type.value,
                    stored.timestamp.isoformat(),
                    self._dumps(stored.payload),
                    stored.sequence,
                ),
            )
        return stored

    def list_events(self, run_id: str) -> list[RuntimeEvent]:
        self.get_run(run_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE run_id = ? ORDER BY sequence ASC", (run_id,)
            ).fetchall()
        return [
            RuntimeEvent(
                event_id=row["event_id"],
                run_id=row["run_id"],
                step_id=row["step_id"],
                event_type=row["event_type"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                payload=self._loads(row["payload_json"]),
                sequence=row["sequence"],
            )
            for row in rows
        ]

    def save_governance_decision(self, decision: GovernanceDecision) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO governance_decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    decision.decision_id,
                    decision.run_id,
                    decision.decision.value,
                    int(decision.allowed),
                    decision.reason,
                    decision.severity.value,
                    self._dumps(decision.matched_policy_ids),
                    self._dumps(decision.metadata),
                    decision.created_at.isoformat(),
                ),
            )

    def save_evaluation(self, evaluation: EvaluationResult) -> None:
        data = evaluation.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO evaluations VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    evaluation.evaluation_id,
                    evaluation.run_id,
                    evaluation.evaluator,
                    int(evaluation.passed),
                    self._dumps(data["findings"]),
                    self._dumps(evaluation.metadata),
                    evaluation.created_at.isoformat(),
                ),
            )

    def save_audit_report(self, report: AuditReport) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_reports VALUES (?, ?, ?, ?, ?)",
                (
                    report.audit_id,
                    report.run_id,
                    self._dumps(report.controls),
                    self._dumps(report.metadata),
                    report.created_at.isoformat(),
                ),
            )

    def save_replay_result(self, replay: ReplayResult) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO replay_runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    replay.replay_id,
                    replay.run_id,
                    replay.status,
                    self._dumps(replay.key_events),
                    self._dumps(replay.metadata),
                    replay.created_at.isoformat(),
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(self.path, isolation_level=None)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as exc:
            raise AilurosStorageError(str(exc)) from exc

    def _row_to_run(self, row: sqlite3.Row) -> Run:
        return Run(
            run_id=row["run_id"],
            agent_id=row["agent_id"],
            environment=row["environment"],
            status=row["status"],
            input=self._loads(row["input_json"]) if row["input_json"] is not None else None,
            user_id=row["user_id"],
            metadata=self._loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _dumps(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True)

    def _loads(self, value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise AilurosDataCorruptionError("stored JSON payload is corrupt") from exc
