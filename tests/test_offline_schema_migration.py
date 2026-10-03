"""Migration 3: public uids, change counters, deletions and processed op_ids."""

import sqlite3
import uuid

import pytest

from database_setup import _migrations, init_database
from migrations import run_migrations

LATEST_VERSION = len(_migrations("unused"))


def _columns(db: sqlite3.Connection, table: str) -> dict[str, tuple]:
    # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
    return {row[1]: row for row in db.execute(f"PRAGMA table_info({table})")}


def _index_names(db: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    }


def _assert_uuid4(value: str) -> None:
    parsed = uuid.UUID(value)
    assert parsed.version == 4
    assert parsed.variant == uuid.RFC_4122
    assert str(parsed) == value  # lowercase, canonical


def _version_two_database(path) -> sqlite3.Connection:
    """A version 2 database with two rooms, lists and items."""
    db = sqlite3.connect(path)
    run_migrations(db, _migrations("pw")[:2])
    home = db.execute("SELECT id FROM rooms").fetchone()[0]
    other = db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES ('Other', 'other', 'x')"
    ).lastrowid
    db.execute(
        "INSERT INTO lists (id, name, slug, room_id, share_token) VALUES "
        "(1, 'Shop', 'shop', ?, 't1'), (2, 'Todo', 'todo', ?, 't2'), "
        "(3, 'Trip', 'trip', ?, 't3')",
        (home, home, other),
    )
    db.execute(
        "INSERT INTO items (id, name, done, list_id, completed_at) VALUES "
        "(1, 'milk', 1, 1, '2026-01-01T00:00:00.000000Z'), (2, 'bread', 0, 1, NULL), "
        "(3, 'tent', 0, 3, NULL)"
    )
    db.commit()
    return db


def test_fresh_database_has_offline_ready_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "fresh.db"))
    db = init_database()

    assert db.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
    room_columns = _columns(db, "rooms")
    assert room_columns["change_seq"][3:5] == (1, "0")
    for table in ("lists", "items"):
        columns = _columns(db, table)
        assert columns["uid"][2] == "TEXT"
        assert columns["changed_seq"][3:5] == (1, "0")
    assert {
        "idx_lists_uid",
        "idx_items_uid",
        "idx_deletions_room_seq",
        "idx_processed_ops_created_at",
    } <= _index_names(db)
    assert set(_columns(db, "deletions")) == {
        "id",
        "room_id",
        "kind",
        "uid",
        "changed_seq",
    }
    assert set(_columns(db, "processed_ops")) == {
        "op_id",
        "room_id",
        "request_hash",
        "response_json",
        "created_at",
    }
    assert db.execute("SELECT change_seq FROM rooms").fetchall() == [(0,)]
    db.close()


def test_upgrade_from_version_two_keeps_data_and_backfills_uids(tmp_path, monkeypatch):
    path = tmp_path / "v2.db"
    db = _version_two_database(path)
    before = {
        table: db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        for table in ("rooms", "lists", "items")
    }
    db.close()

    monkeypatch.setenv("DB_PATH", str(path))
    db = init_database()

    assert db.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
    old_room_columns = "id, name, slug, password_hash, authorization_version"
    assert (
        db.execute(f"SELECT {old_room_columns} FROM rooms ORDER BY id").fetchall()
        == before["rooms"]
    )
    for table in ("lists", "items"):
        rows = db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        # New columns are appended, so the old ones keep their order.
        assert [row[:-2] for row in rows] == before[table]
        uids = [row[-2] for row in rows]
        for uid in uids:
            _assert_uuid4(uid)
        assert len(set(uids)) == len(uids)
        assert {row[-1] for row in rows} == {0}
    assert db.execute("SELECT DISTINCT change_seq FROM rooms").fetchall() == [(0,)]
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    db.close()


def test_rerun_changes_nothing(tmp_path, monkeypatch):
    path = tmp_path / "v2.db"
    _version_two_database(path).close()
    monkeypatch.setenv("DB_PATH", str(path))
    db = init_database()
    uids = db.execute(
        "SELECT uid FROM lists UNION ALL SELECT uid FROM items"
    ).fetchall()
    db.close()

    db = init_database()

    assert db.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
    assert (
        db.execute("SELECT uid FROM lists UNION ALL SELECT uid FROM items").fetchall()
        == uids
    )
    db.close()


def test_uids_are_unique(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "v2.db"))
    _version_two_database(tmp_path / "v2.db").close()
    db = init_database()
    list_uid = db.execute("SELECT uid FROM lists WHERE id = 1").fetchone()[0]
    item_uid = db.execute("SELECT uid FROM items WHERE id = 1").fetchone()[0]

    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE lists SET uid = ? WHERE id = 2", (list_uid,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE items SET uid = ? WHERE id = 2", (item_uid,))
    db.rollback()
    db.close()


def test_room_delete_removes_its_deletions_and_processed_ops(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "fresh.db"))
    db = init_database()
    home = db.execute("SELECT id FROM rooms").fetchone()[0]
    other = db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES ('Other', 'other', 'x')"
    ).lastrowid
    for room_id in (home, other):
        db.execute(
            "INSERT INTO deletions (room_id, kind, uid, changed_seq) "
            "VALUES (?, 'item', ?, 1)",
            (room_id, str(uuid.uuid4())),
        )
        db.execute(
            "INSERT INTO processed_ops (op_id, room_id, request_hash, response_json) "
            "VALUES (?, ?, 'h', '{}')",
            (str(uuid.uuid4()), room_id),
        )
    db.commit()

    db.execute("DELETE FROM rooms WHERE id = ?", (home,))
    db.commit()

    assert db.execute("SELECT room_id FROM deletions").fetchall() == [(other,)]
    assert db.execute("SELECT room_id FROM processed_ops").fetchall() == [(other,)]
    created_at = db.execute("SELECT created_at FROM processed_ops").fetchone()[0]
    assert created_at.endswith("Z") and "T" in created_at
    db.close()


def test_deletion_kind_is_list_or_item(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "fresh.db"))
    db = init_database()
    room_id = db.execute("SELECT id FROM rooms").fetchone()[0]

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO deletions (room_id, kind, uid, changed_seq) "
            "VALUES (?, 'room', 'x', 1)",
            (room_id,),
        )
    db.rollback()
    db.close()
