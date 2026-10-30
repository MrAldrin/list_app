"""Migrations 12-13 preserve names and version Python-lower uniqueness."""

import sqlite3
from contextlib import closing

import pytest
from migration_helpers import migrate_to

import item_names
from migrations import MigrationError, schema_version


def create_old_item(db: sqlite3.Connection, name: str) -> int:
    room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
    list_id = db.execute(
        "INSERT INTO lists (name, slug, room_id, share_token) "
        "VALUES ('Shop', 'shop', ?, 'shop-token')",
        (room_id,),
    ).lastrowid
    columns = {row[1] for row in db.execute("PRAGMA table_info(items)")}
    if "name_key" in columns:
        return db.execute(
            "INSERT INTO items (name, name_key, done, list_id) VALUES (?, ?, 0, ?)",
            (name, name.strip().lower(), list_id),
        ).lastrowid
    return db.execute(
        "INSERT INTO items (name, done, list_id) VALUES (?, 0, ?)",
        (name, list_id),
    ).lastrowid


def test_migration_preserves_names_and_does_not_mark_backfill_as_an_edit():
    with closing(sqlite3.connect(":memory:")) as db, db:
        migrate_to(db, 11)
        item_id = create_old_item(db, "Éggs")
        before_item = db.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        before_seq = db.execute("SELECT change_seq FROM rooms").fetchone()[0]
        db.commit()

        migrate_to(db)

        after_item = db.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        assert after_item[:-1] == before_item
        assert after_item[-1] == "éggs"
        assert db.execute("SELECT change_seq FROM rooms").fetchone()[0] == before_seq
        assert db.execute("PRAGMA user_version").fetchone()[0] == 13
        assert (
            db.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'index' "
                "AND name = 'idx_items_list_name_key'"
            ).fetchone()
            is not None
        )
        assert (
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'index' "
                "AND name = 'idx_items_list_name_nocase'"
            ).fetchone()
            is None
        )


def test_duplicate_key_collision_fails_without_changing_data_or_schema():
    with closing(sqlite3.connect(":memory:")) as db, db:
        migrate_to(db, 11)
        first_id = create_old_item(db, "ẞ")
        list_id = db.execute(
            "SELECT list_id FROM items WHERE id = ?", (first_id,)
        ).fetchone()[0]
        second_id = db.execute(
            "INSERT INTO items (name, done, list_id) VALUES ('ß', 0, ?)", (list_id,)
        ).lastrowid
        db.commit()
        before_items = db.execute(
            "SELECT id, name, done, list_id, changed_seq FROM items ORDER BY id"
        ).fetchall()
        before_seq = db.execute("SELECT change_seq FROM rooms").fetchone()[0]

        with pytest.raises(
            RuntimeError, match=r"items 1 and 2 in list 1 normalize to 'ß'"
        ):
            migrate_to(db)

        assert schema_version(db) == 11
        assert (
            db.execute(
                "SELECT id, name, done, list_id, changed_seq FROM items ORDER BY id"
            ).fetchall()
            == before_items
        )
        assert db.execute("SELECT change_seq FROM rooms").fetchone()[0] == before_seq
        assert "name_key" not in {
            row[1] for row in db.execute("PRAGMA table_info(items)")
        }
        assert (
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'index' "
                "AND name = 'idx_items_list_name_nocase'"
            ).fetchone()
            is not None
        )
        assert second_id != first_id


def test_name_key_guards_match_python_lower_for_direct_sql_writes():
    with closing(sqlite3.connect(":memory:")) as db, db:
        migrate_to(db)
        item_id = create_old_item(db, "milk")

        with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
            db.execute(
                "UPDATE items SET name = 'ẞeta', name_key = 'ẞeta' WHERE id = ?",
                (item_id,),
            )
        assert db.execute(
            "SELECT name, name_key FROM items WHERE id = ?", (item_id,)
        ).fetchone() == ("milk", "milk")

        db.execute(
            "UPDATE items SET name = 'ẞeta', name_key = 'ßeta' WHERE id = ?",
            (item_id,),
        )
        with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
            db.execute("UPDATE items SET name_key = 'ẞeta' WHERE id = ?", (item_id,))
        assert db.execute(
            "SELECT name, name_key FROM items WHERE id = ?", (item_id,)
        ).fetchone() == ("ẞeta", "ßeta")

        with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
            db.execute(
                "INSERT INTO items (name, name_key, done, list_id) "
                "SELECT 'ẞeta', 'ẞeta', 0, list_id FROM items WHERE id = ?",
                (item_id,),
            )


def test_migration_13_refuses_untrimmed_v12_rows_without_changing_schema():
    with closing(sqlite3.connect(":memory:")) as db, db:
        migrate_to(db, 12)
        item_id = create_old_item(db, "\tMilk\t")
        db.commit()
        before_items = db.execute("SELECT * FROM items").fetchall()
        before_schema = db.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()

        with pytest.raises(MigrationError, match=rf"item {item_id} is not trimmed"):
            migrate_to(db)

        assert schema_version(db) == 12
        assert db.execute("SELECT * FROM items").fetchall() == before_items
        assert (
            db.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
            ).fetchall()
            == before_schema
        )
        assert (
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'item_name_key_metadata'"
            ).fetchone()
            is None
        )


def test_migration_13_collision_aborts_without_merging_or_schema_changes(monkeypatch):
    with closing(sqlite3.connect(":memory:")) as db, db:
        migrate_to(db, 12)
        first_id = create_old_item(db, "\u1c89")
        list_id = db.execute(
            "SELECT list_id FROM items WHERE id = ?", (first_id,)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO items (name, name_key, done, list_id) VALUES (?, ?, 0, ?)",
            ("\u1c8a", "\u1c8a", list_id),
        )
        db.commit()
        before_items = db.execute("SELECT * FROM items ORDER BY id").fetchall()
        before_schema = db.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()

        monkeypatch.setattr(
            item_names,
            "item_name_key",
            lambda name: name.strip().replace("\u1c89", "\u1c8a").lower(),
        )
        with pytest.raises(MigrationError, match=r"items 1 and 2 in list 1"):
            migrate_to(db)

        assert schema_version(db) == 12
        assert db.execute("SELECT * FROM items ORDER BY id").fetchall() == before_items
        assert (
            db.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
            ).fetchall()
            == before_schema
        )
        assert (
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'item_name_key_metadata'"
            ).fetchone()
            is None
        )


def test_python_trim_guards_reject_tab_and_nel_edges_from_sql():
    with closing(sqlite3.connect(":memory:")) as db, db:
        migrate_to(db)
        item_id = create_old_item(db, "milk")
        list_id = db.execute(
            "SELECT list_id FROM items WHERE id = ?", (item_id,)
        ).fetchone()[0]

        for name in ("\tBread\t", "\u0085Bread\u0085"):
            with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
                db.execute(
                    "INSERT INTO items (name, name_key, done, list_id) "
                    "VALUES (?, 'bread', 0, ?)",
                    (name, list_id),
                )
            with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
                db.execute(
                    "UPDATE items SET name = ?, name_key = 'milk' WHERE id = ?",
                    (name.replace("Bread", "Milk"), item_id),
                )
        assert db.execute("SELECT name, name_key FROM items").fetchone() == (
            "milk",
            "milk",
        )


def test_item_field_triggers_allow_case_but_keep_other_rules():
    with closing(sqlite3.connect(":memory:")) as db, db:
        migrate_to(db)
        item_id = create_old_item(db, "milk")

        db.execute(
            "UPDATE items SET name = 'Oat Milk', name_key = 'oat milk' WHERE id = ?",
            (item_id,),
        )
        inserted = db.execute(
            "INSERT INTO items (name, name_key, done, list_id) "
            "SELECT 'Éggs', 'éggs', 0, list_id FROM items WHERE id = ?",
            (item_id,),
        )
        assert inserted.lastrowid is not None
        with pytest.raises(sqlite3.IntegrityError, match="breaks a field rule"):
            db.execute("UPDATE items SET quantity = 0 WHERE id = ?", (item_id,))
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            db.execute(
                "INSERT INTO items (name, name_key, done, list_id) "
                "SELECT 'OAT MILK', 'oat milk', 0, list_id FROM items WHERE id = ?",
                (item_id,),
            )
