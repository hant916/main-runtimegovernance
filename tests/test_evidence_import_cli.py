from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from ailuros.cli import app
from ailuros.storage.sqlite_storage import SQLiteStorage

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "evidence_package"
VALID_V1 = FIXTURES / "valid-v1"


def _new_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path)
    storage.init()
    return db_path


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(VALID_V1, dest)
    return dest


def _invoke(db: Path, pkg_dir: Path):
    return CliRunner().invoke(
        app, ["--db", str(db), "import-evidence-package", str(pkg_dir)]
    )


class TestEvidenceImportCli:
    def test_import_creates_run_and_events(self, tmp_path):
        db = _new_db(tmp_path)
        pkg_dir = _copy_fixture(tmp_path)

        result = _invoke(db, pkg_dir)
        data = json.loads(result.stdout)

        assert result.exit_code == 0
        assert data["status"] == "created"
        assert data["run_id"] == "run-v1-001"
        assert data["events_imported"] == 2
        assert data["events_skipped"] == 0

    def test_repeat_import_is_idempotent(self, tmp_path):
        db = _new_db(tmp_path)
        pkg_dir = _copy_fixture(tmp_path)

        first = _invoke(db, pkg_dir)
        assert first.exit_code == 0
        first_data = json.loads(first.stdout)
        assert first_data["status"] == "created"

        second = _invoke(db, pkg_dir)
        assert second.exit_code == 0
        second_data = json.loads(second.stdout)
        assert second_data["status"] == "already_present"
        assert second_data["events_imported"] == 0
        assert second_data["events_skipped"] == 2

    def test_conflict_exits_nonzero(self, tmp_path):
        db = _new_db(tmp_path)
        pkg_dir = _copy_fixture(tmp_path)

        first = _invoke(db, pkg_dir)
        assert first.exit_code == 0
        assert json.loads(first.stdout)["status"] == "created"

        timeline = json.loads((pkg_dir / "timeline.json").read_text(encoding="utf-8"))
        timeline["events"][0]["payload"] = {"input": "changed"}
        (pkg_dir / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")

        second = _invoke(db, pkg_dir)
        assert second.exit_code != 0
        second_data = json.loads(second.stdout)
        assert second_data["status"] == "conflict"

    def test_invalid_not_a_directory(self, tmp_path):
        db = _new_db(tmp_path)
        missing = tmp_path / "not_a_dir"

        result = _invoke(db, missing)
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "invalid"

    def test_invalid_missing_manifest(self, tmp_path):
        db = _new_db(tmp_path)
        pkg_dir = _copy_fixture(tmp_path)
        (pkg_dir / "manifest.json").unlink()

        result = _invoke(db, pkg_dir)
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "invalid"

    def test_invalid_bad_json(self, tmp_path):
        db = _new_db(tmp_path)
        pkg_dir = _copy_fixture(tmp_path)
        (pkg_dir / "manifest.json").write_text("{not valid json", encoding="utf-8")

        result = _invoke(db, pkg_dir)
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "invalid"

    def test_db_override_respected(self, tmp_path):
        db = _new_db(tmp_path)
        pkg_dir = _copy_fixture(tmp_path)

        result = CliRunner().invoke(
            app, ["--db", str(db), "import-evidence-package", str(pkg_dir)]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "created"

        storage = SQLiteStorage(db)
        storage.init()
        stored_run = storage.get_run("run-v1-001")
        assert stored_run.metadata.get("imported_from_package") is True
