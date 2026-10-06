"""Positive counters preserve the old zero-count visibility on upgrade."""

import sqlite3
from pathlib import Path

import pytest

from database_setup import _migrations
from migrations import run_migrations


@pytest.mark.parametrize(
    "mode,age,recent,expected",
    [
        ("age", 0, 4, ("all", 7, 4)),
        ("recent", 3, 0, ("all", 3, 10)),
        ("off", 0, 0, ("off", 7, 10)),
        ("all", 0, 0, ("all", 7, 10)),
        ("age", 3, 0, ("age", 3, 10)),
        ("recent", 0, 4, ("recent", 7, 4)),
        ("age", 3, 4, ("age", 3, 4)),
    ],
)
def test_upgrade_preserves_behavior_and_identity(
    tmp_path: Path, mode: str, age: int, recent: int, expected: tuple[str, int, int]
) -> None:
    with sqlite3.connect(tmp_path / "old.db") as db:
        migrations = _migrations("pw")
        run_migrations(db, migrations[:4])
        room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
        list_id = db.execute(
            "INSERT INTO lists (name, slug, room_id, share_token, hide_done_mode, "
            "hide_done_age_days, hide_done_recent_count) VALUES "
            "('Shop', 'shop', ?, 'secret', ?, ?, ?)",
            (room_id, mode, age, recent),
        ).lastrowid
        db.execute(
            "INSERT INTO items (name, list_id, done, completed_at) "
            "VALUES ('milk', ?, 1, '2026-01-01T00:00:00Z')",
            (list_id,),
        )
        db.commit()
        identity = db.execute("SELECT id, uid, slug, share_token FROM lists").fetchall()
        items = db.execute("SELECT * FROM items").fetchall()
        before_seq = db.execute("SELECT change_seq FROM rooms").fetchone()[0]
        backup = tmp_path / "backup.db"
        run_migrations(db, migrations, backup)
        assert (
            db.execute(
                "SELECT hide_done_mode, hide_done_age_days, hide_done_recent_count FROM lists"
            ).fetchone()
            == expected
        )
        assert (
            db.execute("SELECT id, uid, slug, share_token FROM lists").fetchall()
            == identity
        )
        assert db.execute("SELECT * FROM items").fetchall() == items
        seq = db.execute("SELECT change_seq FROM rooms").fetchone()[0]
        assert seq == before_seq + (1 if age == 0 or recent == 0 else 0)
        if age == 0 or recent == 0:
            assert db.execute("SELECT changed_seq FROM lists").fetchone()[0] == seq
        with sqlite3.connect(backup) as copy:
            assert copy.execute("PRAGMA user_version").fetchone()[0] == 4
            assert copy.execute(
                "SELECT hide_done_mode, hide_done_age_days, hide_done_recent_count FROM lists"
            ).fetchone() == (mode, age, recent)
        run_migrations(db, migrations)
        assert db.execute("SELECT change_seq FROM rooms").fetchone()[0] == seq


@pytest.mark.parametrize("field", ["hide_done_age_days", "hide_done_recent_count"])
@pytest.mark.parametrize("value", [0, -1, 100001, 1.5])
def test_database_guards_invalid_inserts_and_updates(field: str, value: float) -> None:
    with sqlite3.connect(":memory:") as db:
        run_migrations(db, _migrations("pw"))
        room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                f"INSERT INTO lists (name, slug, room_id, {field}) VALUES ('Bad', 'bad', ?, ?)",
                (room_id, value),
            )
        db.execute(
            "INSERT INTO lists (name, slug, room_id) VALUES ('Good', 'good', ?)",
            (room_id,),
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(f"UPDATE lists SET {field} = ?", (value,))
        db.execute(f"UPDATE lists SET {field} = 1")
        db.execute(f"UPDATE lists SET {field} = 100000")
