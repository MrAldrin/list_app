import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from contextlib import closing
from pathlib import Path

import bcrypt
import pytest
from migration_helpers import LATEST_VERSION, migrate_to

import database_setup
import item_names
from database_setup import _backup_path, init_database
from migrations import MigrationError


def _create_item_list(db: sqlite3.Connection) -> int:
    room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
    return db.execute(
        "INSERT INTO lists (name, slug, room_id, share_token) "
        "VALUES ('Shop', 'shop', ?, 'shop-token')",
        (room_id,),
    ).lastrowid


def _insert_key_test_item(db: sqlite3.Connection, list_id: int, name: str) -> int:
    return db.execute(
        "INSERT INTO items (name, name_key, done, list_id) VALUES (?, ?, 0, ?)",
        (name, name.strip().lower(), list_id),
    ).lastrowid


def _insert_key_test_group(db: sqlite3.Connection, room_id: int, name: str) -> int:
    return db.execute(
        "INSERT INTO item_groups (uid, room_id, name, name_key, items_json) "
        "VALUES (?, ?, ?, ?, '[]')",
        (str(uuid.uuid4()), room_id, name, item_names.item_name_key(name)),
    ).lastrowid


def _future_item_name_key(name: str) -> str:
    return name.strip().replace("\u1c89", "\u1c8a").lower()


def test_default_database_path_is_project_relative_from_other_working_directory(
    tmp_path,
):
    project_src = tmp_path / "project" / "src"
    project_src.mkdir(parents=True)
    source_root = Path(__file__).resolve().parents[1]
    shutil.copy(source_root / "src" / "database_setup.py", project_src)
    shutil.copy(source_root / "src" / "config.py", project_src)
    shutil.copy(source_root / "src" / "identifiers.py", project_src)
    shutil.copy(source_root / "src" / "item_names.py", project_src)
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
        [sys.executable, "-c", "import database_setup; database_setup.open_database()"],
        cwd=startup_directory,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert (project_src.parent / "list.db").exists()
    assert not (startup_directory / "list.db").exists()


def test_importing_the_database_module_does_not_open_the_database(tmp_path):
    database = tmp_path / "lazy.db"
    env = os.environ.copy()
    env["DB_PATH"] = str(database)
    env["APP_PASSWORD"] = "test-startup-password"
    env["PYTHON_DOTENV_DISABLED"] = "1"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-c", "import database_setup"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert not database.exists()


def test_fresh_database_is_at_latest_version_with_visibility_columns(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "fresh.db"))
    connection = init_database()

    assert connection.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    list_columns = {
        column[1] for column in connection.execute("PRAGMA table_info(lists)")
    }
    item_columns = {
        column[1] for column in connection.execute("PRAGMA table_info(items)")
    }
    group_columns = {
        column[1] for column in connection.execute("PRAGMA table_info(item_groups)")
    }
    assert {
        "hide_done_mode",
        "hide_done_age_days",
        "hide_done_recent_count",
    } <= list_columns
    assert "completed_at" in item_columns
    assert {
        "uid",
        "room_id",
        "name",
        "name_key",
        "items_json",
        "deleted",
        "changed_seq",
        "deleted_at",
    } <= group_columns
    connection.close()


def test_group_migration_preserves_existing_room_lists_and_items(tmp_path, monkeypatch):
    database_path = tmp_path / "group-upgrade.db"
    backup_path = tmp_path / "group-upgrade-backup.db"
    with closing(sqlite3.connect(database_path)) as old, old:
        migrate_to(old, 14)
        list_id = _create_item_list(old)
        old.execute("UPDATE lists SET tag_mode = 'single' WHERE id = ?", (list_id,))
        _insert_key_test_item(old, list_id, "Milk")

    monkeypatch.setenv("DB_PATH", str(database_path))
    monkeypatch.setenv("DB_BACKUP_PATH", str(backup_path))
    upgraded = init_database()
    assert upgraded.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
    assert upgraded.execute(
        "SELECT name FROM lists WHERE name = 'Shop'"
    ).fetchone() == ("Shop",)
    assert upgraded.execute("SELECT name FROM items").fetchone() == ("Milk",)
    assert upgraded.execute("SELECT tag_mode FROM lists").fetchone() == ("single",)
    assert upgraded.execute("SELECT COUNT(*) FROM item_groups").fetchone()[0] == 0
    upgraded.close()

    with closing(sqlite3.connect(backup_path)) as backup:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 14
        assert backup.execute("SELECT name FROM items").fetchone() == ("Milk",)


def test_group_retention_migration_stamps_existing_tombstones_without_losing_payload():
    with closing(sqlite3.connect(":memory:")) as connection:
        migrate_to(connection, 15)
        room_id = connection.execute("SELECT id FROM rooms").fetchone()[0]
        uid = str(uuid.uuid4())
        connection.execute(
            "INSERT INTO item_groups "
            "(uid, room_id, name, name_key, items_json, deleted) "
            "VALUES (?, ?, 'Old recipe', 'old recipe', '[\"beans\"]', 1)",
            (uid, room_id),
        )
        connection.commit()
        old_seq = connection.execute(
            "SELECT changed_seq FROM item_groups WHERE uid = ?", (uid,)
        ).fetchone()[0]
        old_room_seq = connection.execute(
            "SELECT change_seq FROM rooms WHERE id = ?", (room_id,)
        ).fetchone()[0]

        migrate_to(connection)

        deleted_at, items_json = connection.execute(
            "SELECT deleted_at, items_json FROM item_groups WHERE uid = ?", (uid,)
        ).fetchone()
        assert deleted_at is not None and deleted_at.endswith("Z")
        assert items_json == '["beans"]'
        assert (
            connection.execute(
                "SELECT changed_seq FROM item_groups WHERE uid = ?", (uid,)
            ).fetchone()[0]
            == old_seq
        )
        assert (
            connection.execute(
                "SELECT change_seq FROM rooms WHERE id = ?", (room_id,)
            ).fetchone()[0]
            == old_room_seq
        )


def test_reopening_registers_name_key_guard_and_external_field_updates_work(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "item-name-key.db"
    monkeypatch.setenv("DB_PATH", str(database_path))
    db = init_database()
    room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
    list_id = db.execute(
        "INSERT INTO lists (name, slug, room_id, share_token) "
        "VALUES ('Shop', 'shop', ?, 'shop-token')",
        (room_id,),
    ).lastrowid
    db.execute(
        "INSERT INTO items (name, name_key, done, list_id) "
        "VALUES ('ẞeta', 'ßeta', 0, ?)",
        (list_id,),
    )
    db.commit()
    db.close()

    reopened = init_database()
    with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
        reopened.execute("UPDATE items SET name_key = 'ẞeta'")
    with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
        reopened.execute(
            "UPDATE items SET name = ?, name_key = 'ßeta'", ("\u0085ẞeta\u0085",)
        )
    assert reopened.execute("SELECT name, name_key FROM items").fetchone() == (
        "ẞeta",
        "ßeta",
    )
    reopened.commit()
    reopened.close()

    # A plain SQLite reader/writer can still inspect the DB and update other
    # item fields; only the Python-lower name/key invariant needs the app UDF.
    with closing(sqlite3.connect(database_path)) as external, external:
        assert external.execute("SELECT name FROM items").fetchone()[0] == "ẞeta"
        external.execute("UPDATE items SET quantity = 2")
        assert external.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_v12_upgrade_backs_up_and_a_restored_backup_migrates_again(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "v12.db"
    backup_path = tmp_path / "v12-backup.db"
    with closing(sqlite3.connect(database_path)) as old, old:
        migrate_to(old, 12)
        list_id = _create_item_list(old)
        _insert_key_test_item(old, list_id, "Milk")

    monkeypatch.setenv("DB_PATH", str(database_path))
    monkeypatch.setenv("DB_BACKUP_PATH", str(backup_path))
    upgraded = init_database()
    assert upgraded.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
    assert (
        upgraded.execute(
            "SELECT algorithm_version, unicode_version FROM item_name_key_metadata"
        ).fetchone()
        == database_setup._item_name_key_version()
    )
    upgraded.close()

    with closing(sqlite3.connect(backup_path)) as old_backup:
        assert old_backup.execute("PRAGMA user_version").fetchone()[0] == 12
        assert old_backup.execute("SELECT name, name_key FROM items").fetchone() == (
            "Milk",
            "milk",
        )
        assert (
            old_backup.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'item_name_key_metadata'"
            ).fetchone()
            is None
        )

    restored_path = tmp_path / "restored.db"
    with (
        closing(sqlite3.connect(backup_path)) as source,
        closing(sqlite3.connect(restored_path)) as restored,
    ):
        source.backup(restored)
    monkeypatch.setenv("DB_PATH", str(restored_path))
    restored = init_database()
    assert restored.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
    assert restored.execute("SELECT name, name_key FROM items").fetchone() == (
        "Milk",
        "milk",
    )
    restored.close()


def test_v12_upgrade_collision_keeps_database_and_backup_unchanged(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "v12-collision.db"
    backup_path = tmp_path / "v12-collision-backup.db"
    with closing(sqlite3.connect(database_path)) as old, old:
        migrate_to(old, 12)
        list_id = _create_item_list(old)
        _insert_key_test_item(old, list_id, "\u1c89")
        _insert_key_test_item(old, list_id, "\u1c8a")

    with closing(sqlite3.connect(database_path)) as before:
        before_items = before.execute("SELECT * FROM items ORDER BY id").fetchall()
        before_schema = before.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()

    monkeypatch.setenv("DB_PATH", str(database_path))
    monkeypatch.setenv("DB_BACKUP_PATH", str(backup_path))
    monkeypatch.setattr(item_names, "item_name_key", _future_item_name_key)
    monkeypatch.setattr(
        database_setup, "_item_name_key_version", lambda: (1, "simulated-UCD-16")
    )
    with pytest.raises(MigrationError, match=r"items 1 and 2 in list 1"):
        init_database()

    for path in (database_path, backup_path):
        with closing(sqlite3.connect(path)) as unchanged:
            assert unchanged.execute("PRAGMA user_version").fetchone()[0] == 12
            assert (
                unchanged.execute("SELECT * FROM items ORDER BY id").fetchall()
                == before_items
            )
            assert (
                unchanged.execute(
                    "SELECT type, name, sql FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
                ).fetchall()
                == before_schema
            )


def test_runtime_key_version_change_rebuilds_and_backup_can_be_restored(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "versioned.db"
    backup_path = tmp_path / "versioned-backup.db"
    monkeypatch.setenv("DB_PATH", str(database_path))
    monkeypatch.setenv("DB_BACKUP_PATH", str(backup_path))
    initial = init_database()
    list_id = _create_item_list(initial)
    room_id = initial.execute(
        "SELECT room_id FROM lists WHERE id = ?", (list_id,)
    ).fetchone()[0]
    item_id = _insert_key_test_item(initial, list_id, "\u1c89")
    group_id = _insert_key_test_group(initial, room_id, "\u1c89")
    other_room_id = initial.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES ('Other', 'other', 'hash')"
    ).lastrowid
    other_group_id = _insert_key_test_group(initial, other_room_id, "\u1c8a")
    initial.commit()
    old_version = database_setup._item_name_key_version()
    old_seq = initial.execute("SELECT change_seq FROM rooms").fetchone()[0]
    old_changed_seq = initial.execute(
        "SELECT changed_seq FROM items WHERE id = ?", (item_id,)
    ).fetchone()[0]
    old_group_changed_seq = initial.execute(
        "SELECT changed_seq FROM item_groups WHERE id = ?", (group_id,)
    ).fetchone()[0]
    initial.close()

    monkeypatch.setattr(item_names, "item_name_key", _future_item_name_key)
    monkeypatch.setattr(
        database_setup, "_item_name_key_version", lambda: (1, "simulated-UCD-16")
    )
    upgraded = init_database()
    assert upgraded.execute(
        "SELECT name, name_key FROM items WHERE id = ?", (item_id,)
    ).fetchone() == ("\u1c89", "\u1c8a")
    assert upgraded.execute(
        "SELECT name, name_key FROM item_groups WHERE id = ?", (group_id,)
    ).fetchone() == ("\u1c89", "\u1c8a")
    assert upgraded.execute(
        "SELECT room_id, name_key FROM item_groups WHERE id = ?", (other_group_id,)
    ).fetchone() == (other_room_id, "\u1c8a")
    assert upgraded.execute(
        "SELECT algorithm_version, unicode_version FROM item_name_key_metadata"
    ).fetchone() == (1, "simulated-UCD-16")
    assert upgraded.execute("SELECT change_seq FROM rooms").fetchone()[0] == old_seq
    assert (
        upgraded.execute(
            "SELECT changed_seq FROM items WHERE id = ?", (item_id,)
        ).fetchone()[0]
        == old_changed_seq
    )
    assert (
        upgraded.execute(
            "SELECT changed_seq FROM item_groups WHERE id = ?", (group_id,)
        ).fetchone()[0]
        == old_group_changed_seq
    )
    upgraded.close()

    with closing(sqlite3.connect(backup_path)) as backup:
        assert backup.execute(
            "SELECT name, name_key FROM items WHERE id = ?", (item_id,)
        ).fetchone() == ("\u1c89", "\u1c89")
        assert backup.execute(
            "SELECT name, name_key FROM item_groups WHERE id = ?", (group_id,)
        ).fetchone() == ("\u1c89", "\u1c89")
        assert backup.execute(
            "SELECT name_key FROM item_groups WHERE id = ?", (other_group_id,)
        ).fetchone() == ("\u1c8a",)
        assert (
            backup.execute(
                "SELECT algorithm_version, unicode_version FROM item_name_key_metadata"
            ).fetchone()
            == old_version
        )

    restored_path = tmp_path / "restored-versioned.db"
    with (
        closing(sqlite3.connect(backup_path)) as source,
        closing(sqlite3.connect(restored_path)) as restored,
    ):
        source.backup(restored)
    monkeypatch.setenv("DB_PATH", str(restored_path))
    restored = init_database()
    assert restored.execute(
        "SELECT name_key FROM items WHERE id = ?", (item_id,)
    ).fetchone() == ("\u1c8a",)
    assert restored.execute(
        "SELECT name_key FROM item_groups WHERE id = ?", (group_id,)
    ).fetchone() == ("\u1c8a",)
    assert restored.execute(
        "SELECT name_key FROM item_groups WHERE id = ?", (other_group_id,)
    ).fetchone() == ("\u1c8a",)
    assert restored.execute(
        "SELECT algorithm_version, unicode_version FROM item_name_key_metadata"
    ).fetchone() == (1, "simulated-UCD-16")
    restored.close()


def test_runtime_key_collision_rolls_back_and_keeps_backup_unchanged(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "runtime-collision.db"
    backup_path = tmp_path / "runtime-collision-backup.db"
    monkeypatch.setenv("DB_PATH", str(database_path))
    monkeypatch.setenv("DB_BACKUP_PATH", str(backup_path))
    initial = init_database()
    list_id = _create_item_list(initial)
    room_id = initial.execute(
        "SELECT room_id FROM lists WHERE id = ?", (list_id,)
    ).fetchone()[0]
    _insert_key_test_item(initial, list_id, "milk")
    _insert_key_test_group(initial, room_id, "\u1c89")
    _insert_key_test_group(initial, room_id, "\u1c8a")
    initial.commit()
    before_items = initial.execute("SELECT * FROM items ORDER BY id").fetchall()
    before_groups = initial.execute("SELECT * FROM item_groups ORDER BY id").fetchall()
    before_schema = initial.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    old_version = database_setup._item_name_key_version()
    initial.close()

    monkeypatch.setattr(item_names, "item_name_key", _future_item_name_key)
    monkeypatch.setattr(
        database_setup, "_item_name_key_version", lambda: (1, "simulated-UCD-16")
    )
    with pytest.raises(MigrationError, match=r"groups 1 and 2 in room 1"):
        init_database()

    for path in (database_path, backup_path):
        with closing(sqlite3.connect(path)) as unchanged:
            assert (
                unchanged.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
            )
            assert (
                unchanged.execute("SELECT * FROM items ORDER BY id").fetchall()
                == before_items
            )
            assert (
                unchanged.execute("SELECT * FROM item_groups ORDER BY id").fetchall()
                == before_groups
            )
            assert (
                unchanged.execute(
                    "SELECT type, name, sql FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
                ).fetchall()
                == before_schema
            )
            assert (
                unchanged.execute(
                    "SELECT algorithm_version, unicode_version FROM item_name_key_metadata"
                ).fetchone()
                == old_version
            )


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
    with closing(sqlite3.connect(database_path)) as check:
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
