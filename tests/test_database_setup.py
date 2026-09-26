import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import bcrypt
import pytest

from database_setup import init_database


def test_default_database_path_is_project_relative_from_other_working_directory(
    tmp_path,
):
    project_src = tmp_path / "project" / "src"
    project_src.mkdir(parents=True)
    source_root = Path(__file__).resolve().parents[1]
    shutil.copy(source_root / "src" / "database_setup.py", project_src)
    shutil.copy(source_root / "src" / "config.py", project_src)

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


def test_init_database_migrates_existing_rooms_for_access_tokens(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy-rooms.db"
    legacy_db = sqlite3.connect(database_path)
    legacy_db.executescript(
        """
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            password_hash TEXT NOT NULL
        );
        INSERT INTO rooms (id, name, slug, password_hash)
        VALUES (1, 'Existing room', 'existing-room', 'existing-hash');
        """
    )
    legacy_db.commit()
    legacy_db.close()

    monkeypatch.setenv("DB_PATH", str(database_path))
    migrated_db = init_database()

    assert (
        migrated_db.execute(
            "SELECT authorization_version FROM rooms WHERE id = 1"
        ).fetchone()[0]
        == 1
    )
    token_columns = {
        column[1]
        for column in migrated_db.execute(
            "PRAGMA table_info(room_access_tokens)"
        ).fetchall()
    }
    assert {
        "token_hash",
        "room_id",
        "authorization_version",
        "revoked_at",
    } <= token_columns
    foreign_key = migrated_db.execute(
        "PRAGMA foreign_key_list(room_access_tokens)"
    ).fetchone()
    assert foreign_key[2:5] == ("rooms", "room_id", "id")
    assert foreign_key[6].upper() == "CASCADE"
    migrated_db.close()


def test_init_database_repairs_broken_items_foreign_key(tmp_path, monkeypatch):
    database_path = tmp_path / "broken.db"
    legacy_db = sqlite3.connect(database_path)
    legacy_db.executescript(
        """
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            password_hash TEXT NOT NULL
        );
        INSERT INTO rooms (id, name, slug, password_hash)
        VALUES (1, 'Home', 'home-test', 'hash');

        CREATE TABLE lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            list_tags TEXT NOT NULL DEFAULT '[]',
            slug TEXT UNIQUE,
            room_id INTEGER
        );
        INSERT INTO lists (id, name, list_tags, slug, room_id)
        VALUES (1, 'Groceries', '[]', 'groceries-test', 1);

        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            done BOOLEAN,
            list_id INTEGER NOT NULL,
            active_tags TEXT NOT NULL DEFAULT '[]',
            completed_at TEXT,
            FOREIGN KEY(list_id) REFERENCES lists_old(id)
        );
        INSERT INTO items (
            id, name, description, quantity, done, list_id, active_tags,
            completed_at
        ) VALUES (
            1, 'Apples', 'keep cold', 3, 1, 1, '["fruit"]',
            '2025-01-02T03:04:05.000000Z'
        );
        """
    )
    legacy_db.commit()
    legacy_db.close()

    monkeypatch.setenv("DB_PATH", str(database_path))
    repaired_db = init_database()

    assert repaired_db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert repaired_db.execute("PRAGMA foreign_key_check").fetchall() == []
    foreign_key = repaired_db.execute("PRAGMA foreign_key_list(items)").fetchone()
    assert foreign_key[2:5] == ("lists", "list_id", "id")
    assert repaired_db.execute(
        "SELECT name, list_id, description, quantity, active_tags, completed_at "
        "FROM items"
    ).fetchone() == (
        "Apples",
        1,
        "keep cold",
        3,
        '["fruit"]',
        "2025-01-02T03:04:05.000000Z",
    )

    repaired_db.close()


def test_list_rebuild_preserves_existing_visibility_settings(tmp_path, monkeypatch):
    database_path = tmp_path / "visibility-rebuild.db"
    legacy_db = sqlite3.connect(database_path)
    legacy_db.executescript(
        """
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            password_hash TEXT NOT NULL
        );
        INSERT INTO rooms (id, name, slug, password_hash)
        VALUES (1, 'Home', 'home-test', 'hash');

        CREATE TABLE lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            list_tags TEXT NOT NULL DEFAULT '[]',
            slug TEXT UNIQUE,
            room_id INTEGER,
            hide_done_mode TEXT NOT NULL DEFAULT 'off',
            hide_done_age_days INTEGER NOT NULL DEFAULT 7,
            hide_done_recent_count INTEGER NOT NULL DEFAULT 10
        );
        CREATE UNIQUE INDEX idx_lists_name ON lists(name);
        INSERT INTO lists (
            id, name, list_tags, slug, room_id, hide_done_mode,
            hide_done_age_days, hide_done_recent_count
        ) VALUES (1, 'Groceries', '[]', 'groceries-test', 1, 'age', 3, 12);
        """
    )
    legacy_db.commit()
    legacy_db.close()

    monkeypatch.setenv("DB_PATH", str(database_path))
    migrated_db = init_database()

    assert migrated_db.execute(
        "SELECT hide_done_mode, hide_done_age_days, hide_done_recent_count "
        "FROM lists WHERE id = 1"
    ).fetchone() == ("age", 3, 12)
    migrated_db.close()


def test_init_database_migrates_legacy_visibility_schema_and_reinitializes(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "legacy-visibility.db"
    legacy_db = sqlite3.connect(database_path)
    legacy_db.executescript(
        """
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            password_hash TEXT NOT NULL
        );
        INSERT INTO rooms (id, name, slug, password_hash)
        VALUES (1, 'Home', 'home-test', 'hash');

        CREATE TABLE lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            list_tags TEXT NOT NULL DEFAULT '[]',
            slug TEXT UNIQUE,
            room_id INTEGER
        );
        CREATE UNIQUE INDEX idx_lists_name ON lists(name);
        INSERT INTO lists (id, name, list_tags, slug, room_id)
        VALUES (1, 'Groceries', '[]', 'groceries-test', 1);

        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            done BOOLEAN,
            list_id INTEGER NOT NULL,
            active_tags TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY(list_id) REFERENCES lists(id)
        );
        INSERT INTO items (id, name, done, list_id, active_tags)
        VALUES (1, 'Apples', 1, 1, '[]');
        """
    )
    legacy_db.commit()
    legacy_db.close()

    monkeypatch.setenv("DB_PATH", str(database_path))
    migrated_db = init_database()
    assert migrated_db.execute(
        "SELECT hide_done_mode, hide_done_age_days, hide_done_recent_count "
        "FROM lists WHERE id = 1"
    ).fetchone() == ("off", 7, 10)
    assert migrated_db.execute(
        "SELECT done, completed_at, name FROM items WHERE id = 1"
    ).fetchone() == (1, None, "Apples")
    assert migrated_db.execute("PRAGMA foreign_key_check").fetchall() == []
    migrated_db.close()

    migrated_db = init_database()
    assert migrated_db.execute(
        "SELECT hide_done_mode, hide_done_age_days, hide_done_recent_count "
        "FROM lists WHERE id = 1"
    ).fetchone() == ("off", 7, 10)
    assert migrated_db.execute(
        "SELECT done, completed_at, name FROM items WHERE id = 1"
    ).fetchone() == (1, None, "Apples")
    assert migrated_db.execute("PRAGMA foreign_key_check").fetchall() == []
    migrated_db.close()


def test_init_database_repairs_foreign_key_during_list_migration(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.db"
    legacy_db = sqlite3.connect(database_path)
    legacy_db.executescript(
        """
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            password_hash TEXT NOT NULL
        );
        INSERT INTO rooms (id, name, slug, password_hash)
        VALUES (1, 'Home', 'home-test', 'hash');

        CREATE TABLE lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            list_tags TEXT NOT NULL DEFAULT '[]'
        );
        CREATE UNIQUE INDEX idx_lists_name ON lists(name);
        INSERT INTO lists (id, name, list_tags)
        VALUES (1, 'Groceries', '[]');

        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            done BOOLEAN,
            list_id INTEGER NOT NULL,
            active_tags TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY(list_id) REFERENCES lists(id)
        );
        INSERT INTO items (id, name, done, list_id, active_tags)
        VALUES (1, 'Apples', 0, 1, '[]');
        """
    )
    legacy_db.commit()
    legacy_db.close()

    monkeypatch.setenv("DB_PATH", str(database_path))
    repaired_db = init_database()

    assert repaired_db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert repaired_db.execute("PRAGMA foreign_key_check").fetchall() == []
    foreign_key = repaired_db.execute("PRAGMA foreign_key_list(items)").fetchone()
    assert foreign_key[2:5] == ("lists", "list_id", "id")
    assert repaired_db.execute("SELECT name, list_id FROM items").fetchone() == (
        "Apples",
        1,
    )

    repaired_db.close()
