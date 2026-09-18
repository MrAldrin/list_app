import sqlite3

import bcrypt
import pytest

from database_setup import init_database


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


def test_init_database_repairs_broken_items_foreign_key(tmp_path, monkeypatch):
    database_path = tmp_path / "broken.db"
    legacy_db = sqlite3.connect(database_path)
    legacy_db.executescript(
        """
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            password_hash TEXT NOT NULL
        );
        INSERT INTO rooms (id, name, slug, password_hash)
        VALUES (1, 'Home', 'home-test', 'hash');

        CREATE TABLE lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            list_tags TEXT NOT NULL DEFAULT '[]',
            slug TEXT UNIQUE,
            room_id INTEGER
        );
        INSERT INTO lists (id, name, list_tags, slug, room_id)
        VALUES (1, 'Groceries', '[]', 'groceries-test', 1);

        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            done BOOLEAN,
            list_id INTEGER NOT NULL,
            active_tags TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY(list_id) REFERENCES lists_old(id)
        );
        INSERT INTO items (id, name, done, list_id, active_tags)
        VALUES (1, 'Apples', 0, 1, '[]');
        """
    )
    legacy_db.commit()
    legacy_db.close()

    monkeypatch.setenv("DB_PATH", str(database_path))
    repaired_db = init_database()

    assert repaired_db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert repaired_db.execute("PRAGMA foreign_key_check").fetchall() == []
    foreign_key = repaired_db.execute("PRAGMA foreign_key_list(items)").fetchone()
    assert foreign_key[2:5] == ("lists", "list_id", "id")
    assert repaired_db.execute("SELECT name, list_id FROM items").fetchone() == (
        "Apples",
        1,
    )

    repaired_db.close()


def test_init_database_repairs_foreign_key_during_list_migration(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.db"
    legacy_db = sqlite3.connect(database_path)
    legacy_db.executescript(
        """
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            password_hash TEXT NOT NULL
        );
        INSERT INTO rooms (id, name, slug, password_hash)
        VALUES (1, 'Home', 'home-test', 'hash');

        CREATE TABLE lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            list_tags TEXT NOT NULL DEFAULT '[]'
        );
        CREATE UNIQUE INDEX idx_lists_name ON lists(name);
        INSERT INTO lists (id, name, list_tags)
        VALUES (1, 'Groceries', '[]');

        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            done BOOLEAN,
            list_id INTEGER NOT NULL,
            active_tags TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY(list_id) REFERENCES lists(id)
        );
        INSERT INTO items (id, name, done, list_id, active_tags)
        VALUES (1, 'Apples', 0, 1, '[]');
        """
    )
    legacy_db.commit()
    legacy_db.close()

    monkeypatch.setenv("DB_PATH", str(database_path))
    repaired_db = init_database()

    assert repaired_db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert repaired_db.execute("PRAGMA foreign_key_check").fetchall() == []
    foreign_key = repaired_db.execute("PRAGMA foreign_key_list(items)").fetchone()
    assert foreign_key[2:5] == ("lists", "list_id", "id")
    assert repaired_db.execute("SELECT name, list_id FROM items").fetchone() == (
        "Apples",
        1,
    )

    repaired_db.close()
