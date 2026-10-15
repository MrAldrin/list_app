import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import bcrypt
import pytest

from database_setup import _backup_path, _migrations, init_database


def test_default_database_path_is_project_relative_from_other_working_directory(
    tmp_path,
):
    project_src = tmp_path / "project" / "src"
    project_src.mkdir(parents=True)
    source_root = Path(__file__).resolve().parents[1]
    shutil.copy(source_root / "src" / "database_setup.py", project_src)
    shutil.copy(source_root / "src" / "config.py", project_src)
    shutil.copy(source_root / "src" / "migrations.py", project_src)
    shutil.copy(source_root / "src" / "password_hashing.py", project_src)

    startup_directory = tmp_path / "different-working-directory"
    startup_directory.mkdir()
    env = os.environ.copy()
    env.pop("DB_PATH", None)
    env["APP_PASSWORD"] = "test-startup-password"
    env["PYTHONPATH"] = str(project_src)
    env["PYTHON_DOTENV_DISABLED"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", "import database_setup"],
        cwd=startup_directory,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert (project_src.parent / "list.db").exists()
    assert not (startup_directory / "list.db").exists()


def test_fresh_schema_adds_visibility_and_completion_columns(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "fresh.db"))
    connection = init_database()

    list_columns = {
        column[1] for column in connection.execute("PRAGMA table_info(lists)")
    }
    item_columns = {
        column[1] for column in connection.execute("PRAGMA table_info(items)")
    }
    assert {
        "hide_done_mode",
        "hide_done_age_days",
        "hide_done_recent_count",
    } <= list_columns
    assert "completed_at" in item_columns
    connection.close()


def test_default_room_uses_configured_password_without_resetting_it(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "rooms.db"))
    monkeypatch.setenv("APP_PASSWORD", "initial-app-password")
    db = init_database()
    original_hash = db.execute("SELECT password_hash FROM rooms").fetchone()[0]
    assert bcrypt.checkpw(b"initial-app-password", original_hash.encode())
    db.close()

    monkeypatch.setenv("APP_PASSWORD", "changed-app-password")
    db = init_database()
    assert db.execute("SELECT password_hash FROM rooms").fetchone()[0] == original_hash
    db.close()


@pytest.mark.parametrize("password", [None, "", " \t\n"])
def test_missing_password_leaves_existing_database_untouched(
    tmp_path, monkeypatch, password
):
    database_path = tmp_path / "existing.db"
    monkeypatch.setenv("DB_PATH", str(database_path))
    db = init_database()
    db.close()
    original_contents = database_path.read_bytes()

    if password is None:
        monkeypatch.delenv("APP_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("APP_PASSWORD", password)

    with pytest.raises(RuntimeError, match="APP_PASSWORD must be set and not blank"):
        init_database()
    assert database_path.read_bytes() == original_contents


LATEST_VERSION = len(_migrations("unused"))


def test_fresh_database_is_at_latest_version(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "fresh.db"))
    db = init_database()
    assert db.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    db.close()


def test_legacy_database_with_tables_fails_and_is_left_unchanged(tmp_path, monkeypatch):
    # Version 0 (before versioned migrations) is not upgraded. Its tables
    # already exist, so migration 1 fails and the runner rolls back.
    database_path = tmp_path / "legacy.db"
    legacy_db = sqlite3.connect(database_path)
    legacy_db.executescript(
        """
        CREATE TABLE lists (
            id INTEGER PRIMARY KEY, name TEXT UNIQUE, list_tags TEXT DEFAULT '[]'
        );
        INSERT INTO lists (id, name) VALUES (1, 'Groceries');
        """
    )
    legacy_db.close()
    original_contents = database_path.read_bytes()

    monkeypatch.setenv("DB_PATH", str(database_path))
    with pytest.raises(sqlite3.OperationalError, match="already exists"):
        init_database()

    assert database_path.read_bytes() == original_contents
    with sqlite3.connect(database_path) as check:
        assert check.execute("PRAGMA user_version").fetchone()[0] == 0
        assert "rooms" not in {
            row[0] for row in check.execute("SELECT name FROM sqlite_master")
        }


def test_baseline_runs_only_once(tmp_path, monkeypatch):
    # Before versioning, a deleted Home room came back at every restart.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "once.db"))
    db = init_database()
    db.execute("DELETE FROM rooms WHERE name = 'Home'")
    db.commit()
    db.close()

    db = init_database()
    assert db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0
    assert db.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
    db.close()


def test_backup_path_defaults_next_to_database(monkeypatch):
    monkeypatch.delenv("DB_BACKUP_PATH", raising=False)
    assert _backup_path("/data/list.db") == Path("/data/list-pre-migration.db")
    assert _backup_path(":memory:") is None
    monkeypatch.setenv("DB_BACKUP_PATH", "/data/backups/copy.db")
    assert _backup_path("/data/list.db") == Path("/data/backups/copy.db")


def test_file_database_uses_rollback_journal_and_one_second_lock_wait(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "fresh.db"))
    connection = init_database()
    try:
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 1000
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        connection.close()
