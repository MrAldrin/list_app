"""Migration 6: the database rejects bad values (docs/item-writes.md, "Field rules")."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from migration_helpers import migrate_to

from migrations import schema_version


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(":memory:")) as connection, connection:
        migrate_to(connection)
        connection.execute(
            "INSERT INTO lists (name, slug, room_id, share_token) "
            "VALUES ('Shop', 'shop', 1, 'token')"
        )
        connection.execute(
            "INSERT INTO items (name, done, list_id, completed_at) "
            "VALUES ('milk', 1, 1, '2026-01-01T00:00:00Z')"
        )
        connection.commit()
        yield connection


# Every rule, as a bad value for one column.
BAD_VALUES = [
    ("rooms", "name", None),
    ("rooms", "name", ""),
    ("rooms", "name", " Home"),
    ("rooms", "name", "x" * 101),
    ("rooms", "slug", None),
    ("rooms", "slug", ""),
    ("rooms", "authorization_version", 0),
    ("rooms", "authorization_version", None),
    ("lists", "name", "Shop "),
    ("lists", "name", "x" * 101),
    ("lists", "slug", None),
    ("lists", "room_id", None),
    ("lists", "share_token", None),
    ("lists", "list_tags", "not json"),
    ("lists", "list_tags", '{"a": 1}'),
    ("lists", "list_tags", None),
    ("items", "name", None),
    ("items", "name", ""),
    ("items", "name", "Milk"),
    ("items", "name", " milk"),
    ("items", "name", "x" * 101),
    ("items", "description", None),
    ("items", "description", "x" * 1001),
    ("items", "quantity", 0),
    ("items", "quantity", None),
    ("items", "quantity", 1.5),
    ("items", "done", None),
    ("items", "done", 2),
    ("items", "active_tags", "oops"),
    ("items", "active_tags", None),
]


@pytest.mark.parametrize(("table", "column", "value"), BAD_VALUES)
def test_a_bad_update_is_rejected(db, table, column, value):
    before = db.execute(f"SELECT * FROM {table}").fetchall()
    with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
        db.execute(f"UPDATE {table} SET {column} = ?", (value,))
    assert db.execute(f"SELECT * FROM {table}").fetchall() == before


@pytest.mark.parametrize(("table", "column", "value"), BAD_VALUES)
def test_a_bad_insert_is_rejected(db, table, column, value):
    # Copy the good row, with one bad value.
    columns = [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
    columns = [name for name in columns if name not in ("id", "uid")]
    unique = {"slug": "other", "share_token": "other", "name": "other"}
    select = ", ".join(
        "?" if name == column else f"'{unique[name]}'" if name in unique else name
        for name in columns
    )
    with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
        db.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) "
            f"SELECT {select} FROM {table} LIMIT 1",
            (value,),
        )


def test_good_values_at_the_limits_are_accepted(db):
    db.execute("UPDATE rooms SET name = ?", ("x" * 100,))
    db.execute("UPDATE lists SET name = ?, list_tags = '[]'", ("Ä" * 100,))
    db.execute(
        "UPDATE items SET name = ?, description = ?, quantity = 5, "
        "active_tags = '[\"Dairy\"]'",
        ("é" * 100, "x" * 1000),
    )


def test_an_unchecked_item_has_no_completion_time(db):
    with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
        db.execute("UPDATE items SET done = 0")
    db.execute("UPDATE items SET done = 0, completed_at = NULL")
    # Checked items may have no time: they were checked before times existed.
    db.execute("UPDATE items SET done = 1")


def test_other_columns_update_without_the_check(db):
    # Change tracking writes changed_seq; this must not depend on the rules.
    db.execute("UPDATE items SET changed_seq = changed_seq + 5")
    db.execute("UPDATE rooms SET change_seq = change_seq + 1")


def test_a_bad_stored_row_stops_the_migration_unchanged(tmp_path: Path):
    path = tmp_path / "old.db"
    with closing(sqlite3.connect(path)) as db, db:
        migrate_to(db, 5)
        db.execute(
            "INSERT INTO lists (name, slug, room_id, share_token) "
            "VALUES ('Shop', 'shop', 1, 'token')"
        )
        db.execute("INSERT INTO items (name, done, list_id) VALUES ('Milk', 0, 1)")
        db.execute(
            "INSERT INTO items (name, done, list_id, quantity) VALUES ('eggs', 0, 1, 0)"
        )
        db.commit()
        before = db.execute("SELECT * FROM items").fetchall()

        with pytest.raises(
            RuntimeError,
            match=r"Rows break field rules: items\.name: 1, items\.quantity: 1",
        ):
            migrate_to(db)

        assert schema_version(db) == 5
        assert db.execute("SELECT * FROM items").fetchall() == before
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name LIKE '%field_rules%'"
        ).fetchall()
