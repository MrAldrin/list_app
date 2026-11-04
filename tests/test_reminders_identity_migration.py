"""Migration 16 (personal reminder identity) on a database that is already live."""

import sqlite3
from contextlib import closing
from pathlib import Path

from migration_helpers import migrate_to

from database_setup import _migrations
from migrations import run_migrations, schema_version

NEW_TABLES = {
    "reminder_installations",
    "reminder_enrollments",
    "reminder_processed_ops",
}


def test_migration_16_adds_personal_tables_and_keeps_existing_rooms(tmp_path: Path):
    with closing(sqlite3.connect(tmp_path / "legacy.db")) as db:
        migrate_to(db, 15)
        db.execute(
            "INSERT INTO rooms (name, slug, password_hash) VALUES ('Home', 'home-x', 'h')"
        )
        db.commit()
        before = db.execute("SELECT id, name, slug FROM rooms ORDER BY id").fetchall()

        assert run_migrations(db, _migrations("pw")) == 17

        assert schema_version(db) == 17
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert tables >= NEW_TABLES
        assert db.execute(
            "SELECT id, name, slug FROM rooms ORDER BY id"
        ).fetchall() == (before)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_migration_16_defaults_and_installation_secret_is_hashed_only(tmp_path: Path):
    with closing(sqlite3.connect(tmp_path / "fresh.db")) as db:
        migrate_to(db)
        db.execute(
            "INSERT INTO reminder_installations "
            "(secret_hash, timezone, created_at, expires_at) "
            "VALUES ('hash-only', 'Europe/Oslo', 'now', 'later')"
        )
        row = db.execute(
            "SELECT all_day_time, daily_cap, spacing_minutes, paused, "
            "content_privacy, quiet_start, quiet_end, revision "
            "FROM reminder_installations"
        ).fetchone()

    assert row == ("09:00", 10, 10, 0, "generic", "22:00", "08:00", 1)


def test_migration_16_rejects_out_of_range_device_values(tmp_path: Path):
    with closing(sqlite3.connect(tmp_path / "limits.db")) as db:
        migrate_to(db)
        for column, value in (
            ("daily_cap", 0),
            ("daily_cap", 51),
            ("spacing_minutes", 61),
            ("content_privacy", "lock-screen"),
            ("overdue_repeat_days", 31),
        ):
            try:
                db.execute(
                    f"INSERT INTO reminder_installations (secret_hash, timezone, "
                    f"created_at, expires_at, {column}) VALUES (?, 'UTC', 'n', 'l', ?)",
                    (f"h-{column}-{value}", value),
                )
            except sqlite3.IntegrityError:
                continue
            raise AssertionError(f"{column}={value!r} was accepted")


def test_migration_16_personal_op_scopes_have_separate_uniqueness(tmp_path: Path):
    with closing(sqlite3.connect(tmp_path / "ops.db")) as db:
        migrate_to(db)
        db.execute("PRAGMA foreign_keys = ON")
        db.execute(
            "INSERT INTO reminder_installations "
            "(id, secret_hash, timezone, created_at, expires_at) "
            "VALUES (1, 'h', 'UTC', 'n', 'l')"
        )
        room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
        insert = (
            "INSERT INTO reminder_processed_ops (scope, installation_id, room_id, "
            "op_id, request_hash, response_json, created_at) "
            "VALUES (?, 1, ?, 'same-op', 'h', '{}', 'n')"
        )
        db.execute(insert, ("installation", None))
        db.execute(insert, ("enrollment", room_id))
        for scope, room in (("installation", None), ("enrollment", room_id)):
            try:
                db.execute(insert, (scope, room))
            except sqlite3.IntegrityError:
                continue
            raise AssertionError(f"duplicate {scope} op was accepted")
