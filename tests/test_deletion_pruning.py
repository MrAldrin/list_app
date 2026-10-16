"""Deletion records are pruned after 90 days (migration 7, docs/change-tracking.md).

A client behind the room's pruned seq gets a full snapshot from the changes feed.
"""

import sqlite3
import time

from api_helpers import add_item, changes, create_list, home, write_locked
from migration_helpers import migrate_to
from starlette.testclient import TestClient

import database_crud as crud
import main
import server
from database_setup import db, init_database

AGED = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now', '-91 days')"


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _item_id(list_id: int, name: str) -> int:
    return db.execute(
        "SELECT id FROM items WHERE list_id = ? AND name = ?", (list_id, name)
    ).fetchone()[0]


def _delete_item(list_id: int, name: str) -> tuple[str, int]:
    """Delete an item; return its uid and the room seq after the delete."""
    item_id = _item_id(list_id, name)
    uid = db.execute("SELECT uid FROM items WHERE id = ?", (item_id,)).fetchone()[0]
    write_locked(crud.delete_item_locked, item_id, list_id)
    return uid, crud.get_room_seq_locked(home()[0])


def _age(uid: str) -> None:
    db.execute(f"UPDATE deletions SET created_at = {AGED} WHERE uid = ?", (uid,))
    db.commit()


def _deletion_uids() -> set[str]:
    return {row[0] for row in db.execute("SELECT uid FROM deletions")}


def test_fresh_database_has_pruning_columns(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "fresh.db"))
    connection = init_database()

    assert "deletions_pruned_seq" in _columns(connection, "rooms")
    assert "created_at" in _columns(connection, "deletions")
    connection.close()


def test_upgrade_keeps_old_records_and_stamps_them_with_the_migration_time(
    tmp_path, monkeypatch
):
    path = tmp_path / "v6.db"
    old = sqlite3.connect(path)
    migrate_to(old, 6)
    home_id = old.execute("SELECT id FROM rooms").fetchone()[0]
    old.execute(
        "INSERT INTO lists (id, name, slug, room_id, share_token) "
        "VALUES (1, 'Shop', 'shop', ?, 't1')",
        (home_id,),
    )
    old.execute("INSERT INTO items (id, name, done, list_id) VALUES (1, 'milk', 0, 1)")
    old.execute("DELETE FROM items WHERE id = 1")  # the version 4 trigger records it
    old.commit()
    old.close()

    monkeypatch.setenv("DB_PATH", str(path))
    connection = init_database()

    rows = connection.execute("SELECT kind, created_at FROM deletions").fetchall()
    assert [row[0] for row in rows] == ["item"]
    assert rows[0][1] is not None and rows[0][1].endswith("Z")
    assert connection.execute("SELECT deletions_pruned_seq FROM rooms").fetchall() == [
        (0,)
    ]
    # A delete after the upgrade is stamped too.
    connection.execute(
        "INSERT INTO lists (id, name, slug, room_id, share_token) "
        "VALUES (2, 'Todo', 'todo', ?, 't2')",
        (home_id,),
    )
    connection.execute(
        "INSERT INTO items (id, name, done, list_id) VALUES (2, 'bread', 0, 2)"
    )
    connection.execute("DELETE FROM items WHERE id = 2")
    created = connection.execute(
        "SELECT created_at FROM deletions WHERE changed_seq = "
        "(SELECT MAX(changed_seq) FROM deletions)"
    ).fetchone()[0]
    assert created is not None
    connection.close()


def test_prune_removes_only_records_older_than_90_days(room):
    room_id, _, _ = room
    list_id, _ = create_list("Shop", room_id)
    add_item(list_id, "milk")
    add_item(list_id, "bread")
    old_uid, old_seq = _delete_item(list_id, "milk")
    recent_uid, _ = _delete_item(list_id, "bread")
    _age(old_uid)

    assert crud.prune_deletions() == 1

    assert _deletion_uids() == {recent_uid}
    pruned = db.execute("SELECT deletions_pruned_seq FROM rooms").fetchone()[0]
    assert pruned == old_seq


def test_prune_without_old_records_changes_nothing(room):
    room_id, _, _ = room
    list_id, _ = create_list("Shop", room_id)
    add_item(list_id, "milk")
    _delete_item(list_id, "milk")

    assert crud.prune_deletions() == 0
    assert db.execute("SELECT deletions_pruned_seq FROM rooms").fetchone()[0] == 0


def test_prune_takes_every_record_up_to_the_newest_old_one(room):
    room_id, _, _ = room
    list_id, _ = create_list("Shop", room_id)
    for name in ("milk", "bread"):
        add_item(list_id, name)
    first_uid, _ = _delete_item(list_id, "milk")
    second_uid, second_seq = _delete_item(list_id, "bread")
    _age(second_uid)  # the newer record is old; the older one is recent

    assert crud.prune_deletions() == 2

    assert _deletion_uids() == set()
    assert first_uid not in _deletion_uids()
    assert (
        db.execute("SELECT deletions_pruned_seq FROM rooms").fetchone()[0] == second_seq
    )


def test_old_client_gets_a_full_snapshot_after_pruning(room):
    room_id, slug, client = room
    list_id, _ = create_list("Shop", room_id)
    add_item(list_id, "milk")
    add_item(list_id, "bread")
    since_before = changes(client, slug, 0)["seq"]
    old_uid, _ = _delete_item(list_id, "milk")
    _delete_item(list_id, "bread")
    _age(old_uid)
    crud.prune_deletions()

    feed = changes(client, slug, since_before)

    assert feed["full"] is True
    assert feed["deletions"] == []
    assert feed["lists"] and feed["items"] == []


def test_recent_client_gets_a_delta_after_pruning(room):
    room_id, slug, client = room
    list_id, _ = create_list("Shop", room_id)
    add_item(list_id, "milk")
    add_item(list_id, "bread")
    old_uid, seq_after_old = _delete_item(list_id, "milk")
    recent_uid, _ = _delete_item(list_id, "bread")
    _age(old_uid)
    crud.prune_deletions()

    feed = changes(client, slug, seq_after_old)

    assert feed["full"] is False
    assert feed["deletions"] == [{"kind": "item", "uid": recent_uid}]


def test_startup_prunes_deletions_and_the_daily_task_repeats_it(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "prune_deletions", lambda: calls.append(1))
    monkeypatch.setattr(server, "PRUNE_EVERY_SECONDS", 0.01)
    with TestClient(main.app):
        deadline = time.monotonic() + 5
        while len(calls) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
    assert len(calls) >= 2
