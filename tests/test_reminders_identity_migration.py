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

        assert run_migrations(db, _migrations("pw")) == 18

        assert schema_version(db) == 18
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


def test_migration_18_populated_upgrade_preserves_settings_and_historical_cutoffs(
    tmp_path, monkeypatch
):
    from datetime import UTC, datetime

    from reminders import identity, policies
    from reminders.rules import RelativeRule

    with closing(sqlite3.connect(tmp_path / "v17.db")) as db:
        db.execute("PRAGMA foreign_keys = ON")
        migrate_to(db, 17)
        room_id = db.execute("SELECT id FROM rooms LIMIT 1").fetchone()[0]
        list_id = db.execute(
            "INSERT INTO lists (name, slug, room_id, share_token) VALUES ('Test', 'test', ?, 'share')",
            (room_id,),
        ).lastrowid
        db.execute(
            "INSERT INTO items (name, name_key, done, list_id, date, due_cycle, due_cycle_started_at) VALUES ('dated', 'dated', 0, ?, '2027-01-01', 'cycle', '2026-01-02T12:00:00Z')",
            (list_id,),
        )
        created = "2026-01-01T10:00:00Z"
        activated = "2026-01-02T10:00:00Z"
        for installation, mode in enumerate(
            ("quiet", "daily_summary", "scheduled", "custom"), 1
        ):
            db.execute(
                "INSERT INTO reminder_installations (id, secret_hash, timezone, all_day_time, daily_cap, paused, content_privacy, revision, created_at, expires_at) VALUES (?, ?, 'Europe/Oslo', '11:15', 23, 1, 'names', 3, ?, '2030-01-01T00:00:00Z')",
                (installation, f"hash-{installation}", created),
            )
            db.execute(
                "INSERT INTO reminder_enrollments (installation_id, room_id, token_hash, authorization_version, status, mode, summary_time, revision, activated_at, expires_at, created_at) VALUES (?, ?, 'token', 1, 'active', ?, '08:15', 4, ?, '2030-01-01T00:00:00Z', ?)",
                (installation, room_id, mode, activated, created),
            )
        db.commit()
        before_installations = db.execute(
            "SELECT * FROM reminder_installations ORDER BY id"
        ).fetchall()
        before_enrollments = db.execute(
            "SELECT * FROM reminder_enrollments ORDER BY installation_id"
        ).fetchall()
        before_items = db.execute("SELECT * FROM items ORDER BY id").fetchall()
        before_seq = db.execute(
            "SELECT change_seq FROM rooms WHERE id = ?", (room_id,)
        ).fetchone()[0]
        assert run_migrations(db, _migrations("pw")) == 18
        assert schema_version(db) == 18
        installations = db.execute(
            "SELECT * FROM reminder_installations ORDER BY id"
        ).fetchall()
        enrollments = db.execute(
            "SELECT * FROM reminder_enrollments ORDER BY installation_id"
        ).fetchall()
        assert [row[:-2] for row in installations] == before_installations
        assert [row[-2:] for row in installations] == [(created, created)] * 4
        assert [row[:-2] for row in enrollments] == before_enrollments
        assert [row[-2:] for row in enrollments] == [(activated, activated)] * 4
        assert db.execute("SELECT * FROM items ORDER BY id").fetchall() == before_items
        assert (
            db.execute(
                "SELECT change_seq FROM rooms WHERE id = ?", (room_id,)
            ).fetchone()[0]
            == before_seq
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert datetime.fromisoformat(created).tzinfo == UTC
        assert datetime.fromisoformat(activated).tzinfo == UTC
        monkeypatch.setattr(identity, "db", db)
        monkeypatch.setattr(policies, "db", db)
        for installation, mode in enumerate(
            ("quiet", "daily_summary", "scheduled", "custom"), 1
        ):
            policy = policies.policy_locked(installation, room_id, "room")
            assert (
                policy.state,
                policy.preset,
                policy.revision,
                policy.activated_at,
            ) == ("replace", mode, 0, datetime.fromisoformat(activated))
            assert policy.summary_enabled == (mode == "daily_summary")
            assert policy.rules == (
                (RelativeRule("calendar", 1), RelativeRule("at_due", 0))
                if mode == "scheduled"
                else ()
            )
