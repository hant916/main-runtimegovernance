from __future__ import annotations

import json
import shutil
from pathlib import Path

from ailuros.backfill import BatchSummary, batch_import_project, discover_packages
from ailuros.storage.sqlite_storage import SQLiteStorage

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "evidence_package"
VALID_V1 = FIXTURES / "valid-v1"
VALID_V15 = FIXTURES / "valid-v15"


def _new_storage(tmp_path: Path) -> SQLiteStorage:
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path)
    storage.init()
    return storage


def _copy_fixture(fixture: Path, dest: Path) -> None:
    shutil.copytree(fixture, dest)


def _make_package_stub(
    root: Path,
    name: str,
    run_id: str,
    source: str = "test-agent",
    events: list | None = None,
    manifest_overrides: dict | None = None,
) -> Path:
    pkg_dir = root / name
    pkg_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "package_version": "1",
        "source": source,
        "target": "ailuros",
        "governance_mode": "observe",
        "schema_version": "ailuros.timeline.v1",
        "run_id": run_id,
        "generated_at": "2025-01-15T10:01:30+00:00",
        "files": [
            {"name": "manifest.json", "required": True},
            {"name": "timeline.json", "required": True},
        ],
        "metadata": {},
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)

    if events is None:
        events = [
            {
                "event_id": f"{run_id}-evt-1",
                "event_type": "run_started",
                "timestamp": "2025-01-15T10:00:00+00:00",
                "payload": {},
                "metadata": {},
            },
            {
                "event_id": f"{run_id}-evt-2",
                "event_type": "run_completed",
                "timestamp": "2025-01-15T10:01:00+00:00",
                "payload": {},
                "metadata": {},
            },
        ]

    timeline = {
        "schema_version": "ailuros.timeline.v1",
        "run_id": run_id,
        "events": events,
    }

    (pkg_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (pkg_dir / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
    return pkg_dir


def _make_invalid_package_stub(root: Path, name: str) -> Path:
    pkg_dir = root / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "manifest.json").write_text("not valid json", encoding="utf-8")
    (pkg_dir / "timeline.json").write_text("not valid json", encoding="utf-8")
    return pkg_dir


# ── discover_packages ──────────────────────────────────────────────────────


class TestDiscoverPackages:
    def test_finds_valid_child_dirs(self, tmp_path: Path) -> None:
        _make_package_stub(tmp_path, "pkg-a", "run-a")
        _make_package_stub(tmp_path, "pkg-b", "run-b")
        (tmp_path / "not-a-package").mkdir()

        results = discover_packages(tmp_path)
        assert len(results) == 2
        names = {d.name for d in results}
        assert names == {"pkg-a", "pkg-b"}

    def test_skips_dirs_without_manifest(self, tmp_path: Path) -> None:
        d = tmp_path / "incomplete"
        d.mkdir()
        (d / "timeline.json").write_text("{}", encoding="utf-8")

        assert discover_packages(tmp_path) == []

    def test_skips_dirs_without_timeline(self, tmp_path: Path) -> None:
        d = tmp_path / "incomplete"
        d.mkdir()
        (d / "manifest.json").write_text("{}", encoding="utf-8")

        assert discover_packages(tmp_path) == []

    def test_skips_files(self, tmp_path: Path) -> None:
        (tmp_path / "somefile.txt").write_text("hi", encoding="utf-8")
        assert discover_packages(tmp_path) == []

    def test_nonexistent_dir(self) -> None:
        assert discover_packages("/nonexistent/path/12345") == []

    def test_returns_sorted(self, tmp_path: Path) -> None:
        _make_package_stub(tmp_path, "z-pkg", "run-z")
        _make_package_stub(tmp_path, "a-pkg", "run-a")
        _make_package_stub(tmp_path, "m-pkg", "run-m")

        results = discover_packages(tmp_path)
        names = [d.name for d in results]
        assert names == ["a-pkg", "m-pkg", "z-pkg"]


# ── batch_import_project ───────────────────────────────────────────────────


class TestBatchImportProject:
    def test_imports_all_packages(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        _make_package_stub(tmp_path, "pkg-a", "run-a")
        _make_package_stub(tmp_path, "pkg-b", "run-b")

        summary = batch_import_project(storage, tmp_path)

        assert summary.total == 2
        assert summary.created == 2
        assert summary.already_present == 0
        assert summary.invalid == 0
        assert summary.conflict == 0
        assert summary.projected == 2
        assert summary.projection_failed == 0

        assert len(storage.list_events("run-a")) == 2
        assert len(storage.list_events("run-b")) == 2

    def test_idempotent_second_run(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        _make_package_stub(tmp_path, "pkg-a", "run-a")

        first = batch_import_project(storage, tmp_path)
        assert first.created == 1
        assert first.already_present == 0

        second = batch_import_project(storage, tmp_path)
        assert second.created == 0
        assert second.already_present == 1
        assert second.projected == 1

        assert len(storage.list_events("run-a")) == 2

    def test_invalid_package_recorded(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        _make_package_stub(tmp_path, "pkg-good", "run-good")
        _make_invalid_package_stub(tmp_path, "pkg-bad")

        summary = batch_import_project(storage, tmp_path)

        assert summary.total == 2
        assert summary.created == 1
        assert summary.invalid == 1
        assert len(summary.failures) == 1
        assert summary.failures[0]["stage"] == "load"
        assert "pkg-bad" in summary.failures[0]["package_dir"]

    def test_conflict_package_recorded(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        pkg_dir = _make_package_stub(tmp_path, "pkg-a", "run-a")
        _make_package_stub(tmp_path, "pkg-b", "run-b")

        batch_import_project(storage, tmp_path)

        timeline = json.loads((pkg_dir / "timeline.json").read_text(encoding="utf-8"))
        timeline["events"][0]["payload"] = {"changed": True}
        (pkg_dir / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")

        summary = batch_import_project(storage, tmp_path)
        assert summary.conflict >= 1

    def test_conflict_skips_projection(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        pkg_dir = _make_package_stub(tmp_path, "pkg-a", "run-a")

        batch_import_project(storage, tmp_path)
        assert storage.get_projection("run-a") is not None

        timeline = json.loads((pkg_dir / "timeline.json").read_text(encoding="utf-8"))
        timeline["events"][0]["payload"] = {"changed": True}
        (pkg_dir / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")

        summary = batch_import_project(storage, tmp_path)
        assert summary.conflict == 1
        assert summary.projected == 0

    def test_empty_directory(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        summary = batch_import_project(storage, tmp_path)

        assert summary.total == 0
        assert summary.created == 0
        assert summary.already_present == 0
        assert summary.invalid == 0
        assert summary.conflict == 0
        assert summary.projected == 0
        assert summary.projection_failed == 0

    def test_rebuilds_projection_on_created(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        _make_package_stub(tmp_path, "pkg-a", "run-a")

        batch_import_project(storage, tmp_path)

        proj = storage.get_projection("run-a")
        assert proj is not None
        assert proj["projection"]["run_id"] == "run-a"

    def test_rebuilds_projection_on_already_present(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        _make_package_stub(tmp_path, "pkg-a", "run-a")

        batch_import_project(storage, tmp_path)
        storage.get_projection("run-a")  # exists

        summary = batch_import_project(storage, tmp_path)
        assert summary.already_present == 1
        assert summary.projected == 1

    def test_failure_continues_to_next_package(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        _make_invalid_package_stub(tmp_path, "pkg-bad")
        _make_package_stub(tmp_path, "pkg-good", "run-good")

        summary = batch_import_project(storage, tmp_path)

        assert summary.total == 2
        assert summary.created == 1
        assert summary.invalid == 1

        assert len(storage.list_events("run-good")) == 2

    def test_coverage_aggregation(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        _make_package_stub(
            tmp_path,
            "pkg-a",
            "run-a",
            manifest_overrides={
                "pkg_metadata": {"coverage": {"events": 2, "files": 3}},
            },
        )
        _make_package_stub(
            tmp_path,
            "pkg-b",
            "run-b",
            manifest_overrides={
                "pkg_metadata": {"coverage": {"events": 3, "files": 2}},
            },
        )

        summary = batch_import_project(storage, tmp_path)

        assert summary.coverage.get("events") == 5
        assert summary.coverage.get("files") == 5

    def test_coverage_with_nested(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        _make_package_stub(
            tmp_path,
            "pkg-a",
            "run-a",
            manifest_overrides={
                "pkg_metadata": {"coverage": {"mapping": {"decisions": 1}}},
            },
        )
        _make_package_stub(
            tmp_path,
            "pkg-b",
            "run-b",
            manifest_overrides={
                "pkg_metadata": {"coverage": {"mapping": {"decisions": 2}}},
            },
        )

        summary = batch_import_project(storage, tmp_path)

        assert summary.coverage == {"mapping": {"decisions": 3}}

    def test_no_coverage_when_missing(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        _make_package_stub(tmp_path, "pkg-a", "run-a")

        summary = batch_import_project(storage, tmp_path)

        assert summary.coverage == {}

    def test_import_events_use_proper_event_type(self, tmp_path: Path) -> None:
        storage = _new_storage(tmp_path)
        _make_package_stub(tmp_path, "pkg-a", "run-a")

        batch_import_project(storage, tmp_path)

        events = storage.list_events("run-a")
        assert len(events) == 2
        assert all(e.event_type.value == "external_evidence" for e in events)

    def test_batch_summary_defaults(self) -> None:
        s = BatchSummary()
        assert s.total == 0
        assert s.created == 0
        assert s.already_present == 0
        assert s.invalid == 0
        assert s.conflict == 0
        assert s.projected == 0
        assert s.projection_failed == 0
        assert s.failures == []
        assert s.coverage == {}
