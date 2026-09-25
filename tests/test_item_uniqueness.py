import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from database_crud import add_item, add_or_restore_item_atomic, db, update_item_done
from database_setup import init_database
from item_service import add_or_restore_item


def test_simultaneous_adds_and_restores_keep_one_item():
    list_id = db.execute("SELECT id FROM lists").fetchone()[0]
    barrier = Barrier(8)

    def submit(_: int) -> str:
        barrier.wait()
        return add_or_restore_item(list_id, " Milk ")[0]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))
    assert results.count("added") == 1
    assert results.count("duplicate_active") == 7
    item_id, done = db.execute(
        "SELECT id, done FROM items WHERE list_id = ?", (list_id,)
    ).fetchone()
    assert done == 0

    update_item_done(item_id, list_id, True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))
    assert results.count("restored") == 1
    assert results.count("duplicate_active") == 7
    assert (
        db.execute(
            "SELECT COUNT(*) FROM items WHERE list_id = ?", (list_id,)
        ).fetchone()[0]
        == 1
    )


def test_unique_index_rejects_case_and_whitespace_but_allows_other_lists():
    list_id = db.execute("SELECT id FROM lists").fetchone()[0]
    add_item("milk", list_id)
    with pytest.raises(sqlite3.IntegrityError):
        add_item(" Milk ", list_id)
    other = db.execute(
        "INSERT INTO lists (name, room_id) SELECT 'other', room_id FROM lists WHERE id = ?",
        (list_id,),
    ).lastrowid
    db.commit()
    add_item("MILK", other)
    assert add_or_restore_item_atomic("milk", list_id) == "duplicate_active"


def test_migration_rejects_existing_duplicates_without_removing_them(
    tmp_path, monkeypatch
):
    path = tmp_path / "duplicates.db"
    monkeypatch.setenv("DB_PATH", str(path))
    connection = init_database()
    room_id = connection.execute("SELECT id FROM rooms LIMIT 1").fetchone()[0]
    list_id = connection.execute(
        "INSERT INTO lists (name, room_id) VALUES ('groceries', ?)", (room_id,)
    ).lastrowid
    connection.execute("DROP INDEX idx_items_list_name_nocase")
    connection.execute(
        "INSERT INTO items (list_id, name) VALUES (?, 'Milk')", (list_id,)
    )
    connection.execute(
        "INSERT INTO items (list_id, name) VALUES (?, ' milk ')", (list_id,)
    )
    connection.commit()
    connection.close()

    with pytest.raises(sqlite3.IntegrityError, match="resolve duplicates first"):
        init_database()
    with sqlite3.connect(path) as check:
        assert check.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2
        assert (
            check.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name = 'idx_items_list_name_nocase'"
            ).fetchone()[0]
            == 0
        )
