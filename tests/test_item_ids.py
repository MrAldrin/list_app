"""Deleted item IDs are never reused, so stale item actions cannot hit new items."""

import sqlite3

import pytest

import database_crud as crud
from database_setup import _migration_1_baseline, init_database
from migrations import run_migrations


@pytest.fixture
def list_id():
    room_id = crud.get_rooms()[0]["id"]
    return crud.create_list("groceries", room_id)[0]


def _items(list_id):
    return crud.get_list_data(list_id)


@pytest.fixture
def stale_and_replacement(list_id):
    crud.add_item("old", list_id)
    old_id = crud.find_item_by_name(list_id, "old")[0]
    crud.delete_item(old_id, list_id)
    crud.add_item("replacement", list_id)
    new_id = crud.find_item_by_name(list_id, "replacement")[0]
    return old_id, new_id


def test_new_item_does_not_reuse_deleted_newest_id(stale_and_replacement):
    old_id, new_id = stale_and_replacement
    assert new_id > old_id


@pytest.mark.parametrize(
    "stale_action",
    [
        lambda item_id, list_id: crud.toggle_item_active_tag(item_id, list_id, "x"),
        lambda item_id, list_id: crud.update_item_done(item_id, list_id, True),
        lambda item_id, list_id: crud.adjust_item_quantity(item_id, list_id, 2),
        lambda item_id, list_id: crud.update_item_quantity(item_id, list_id, 5),
        lambda item_id, list_id: crud.update_item_details(
            item_id, list_id, "renamed", "note"
        ),
        lambda item_id, list_id: crud.delete_item(item_id, list_id),
    ],
    ids=["tag", "done", "adjust-qty", "set-qty", "edit", "delete"],
)
def test_stale_item_action_leaves_replacement_unchanged(
    list_id, stale_and_replacement, stale_action
):
    old_id, _ = stale_and_replacement
    before = _items(list_id)

    stale_action(old_id, list_id)

    assert _items(list_id) == before


def _version_one_database(path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    run_migrations(db, [lambda db: _migration_1_baseline(db, "pw")])
    return db


def test_migration_keeps_items_and_indexes_and_stops_id_reuse(tmp_path, monkeypatch):
    path = tmp_path / "list.db"
    db = _version_one_database(path)
    room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
    db.execute(
        "INSERT INTO lists (id, name, room_id) VALUES (1, 'Shop', ?)", (room_id,)
    )
    db.execute(
        "INSERT INTO items (id, name, description, quantity, done, list_id, "
        "active_tags, completed_at) VALUES "
        "(1, 'Milk', 'cold', 2, 1, 1, '[\"a\"]', '2026-01-01T00:00:00Z'), "
        "(2, 'Bread', '', 1, 0, 1, '[]', NULL)"
    )
    db.commit()
    rows_before = db.execute("SELECT * FROM items ORDER BY id").fetchall()
    indexes_before = db.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'index' "
        "AND tbl_name = 'items' ORDER BY name"
    ).fetchall()
    db.close()

    monkeypatch.setenv("DB_PATH", str(path))
    db = init_database()

    assert db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert db.execute("SELECT * FROM items ORDER BY id").fetchall() == rows_before
    assert (
        db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'index' "
            "AND tbl_name = 'items' ORDER BY name"
        ).fetchall()
        == indexes_before
    )
    assert db.execute("PRAGMA foreign_key_list(items)").fetchone()[2:5] == (
        "lists",
        "list_id",
        "id",
    )
    db.execute("DELETE FROM items WHERE id = 2")
    new_id = db.execute(
        "INSERT INTO items (name, list_id) VALUES ('Eggs', 1)"
    ).lastrowid
    assert new_id == 3
    db.close()


def test_fresh_database_uses_autoincrement(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "fresh.db"))
    db = init_database()
    items_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'items'"
    ).fetchone()[0]
    assert "AUTOINCREMENT" in items_sql
    db.close()
