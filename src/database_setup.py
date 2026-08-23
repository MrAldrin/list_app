import os
import re
import sqlite3
import uuid

import bcrypt
from dotenv import load_dotenv

# Load env variables so we can use APP_PASSWORD for default room migration if run directly
load_dotenv()


def _create_slug(name: str) -> str:
    safe_name = re.sub(r"[^a-z0-9]", "-", name.lower().strip())
    short_uuid = str(uuid.uuid4())[:6]
    return f"{safe_name}-{short_uuid}"


def _ensure_default_room(db: sqlite3.Connection) -> int:
    existing_room = db.execute("SELECT id FROM rooms WHERE name = 'Home'").fetchone()
    if existing_room:
        return existing_room[0]

    global_pw = os.environ.get("APP_PASSWORD", "dev_password")
    pw_hash = bcrypt.hashpw(global_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    insert = db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
        ("Home", _create_slug("Home"), pw_hash),
    )
    return insert.lastrowid


def _backfill_list_slugs(db: sqlite3.Connection) -> None:
    rows = db.execute("SELECT id, name FROM lists WHERE slug IS NULL").fetchall()
    for list_id, name in rows:
        db.execute(
            "UPDATE lists SET slug = ? WHERE id = ?", (_create_slug(name), list_id)
        )


def _lists_name_is_globally_unique(db: sqlite3.Connection) -> bool:
    indexes = db.execute("PRAGMA index_list(lists)").fetchall()
    for idx in indexes:
        # PRAGMA index_list columns: seq, name, unique, origin, partial
        idx_name = idx[1]
        is_unique = idx[2] == 1
        if not is_unique:
            continue
        cols = db.execute(f"PRAGMA index_info({idx_name!r})").fetchall()
        if len(cols) == 1 and cols[0][2] == "name":
            return True
    return False


def _migrate_lists_to_room_scoped_names(db: sqlite3.Connection) -> None:
    db.execute("ALTER TABLE lists RENAME TO lists_old")
    db.execute(
        """
        CREATE TABLE lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            list_tags TEXT NOT NULL DEFAULT '[]',
            slug TEXT UNIQUE,
            room_id INTEGER
        )
        """
    )
    db.execute(
        """
        INSERT INTO lists (id, name, list_tags, slug, room_id)
        SELECT id, name, list_tags, slug, room_id
        FROM lists_old
        """
    )
    db.execute("DROP TABLE lists_old")


def init_database():
    db_path = os.environ.get("DB_PATH", "list.db")
    db = sqlite3.connect(db_path, check_same_thread=False)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            password_hash TEXT NOT NULL
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            list_tags TEXT NOT NULL DEFAULT '[]',
            slug TEXT UNIQUE,
            room_id INTEGER
        )
        """
    )

    # Migrations for legacy schema variants
    cursor = db.execute("PRAGMA table_info(lists)")
    columns = [col[1] for col in cursor.fetchall()]
    if "slug" not in columns:
        db.execute("ALTER TABLE lists ADD COLUMN slug TEXT")
    _backfill_list_slugs(db)

    if "room_id" not in columns:
        db.execute("ALTER TABLE lists ADD COLUMN room_id INTEGER")

    default_room_id = _ensure_default_room(db)
    db.execute("UPDATE lists SET room_id = ? WHERE room_id IS NULL", (default_room_id,))

    if _lists_name_is_globally_unique(db):
        _migrate_lists_to_room_scoped_names(db)
        db.execute(
            "UPDATE lists SET room_id = ? WHERE room_id IS NULL", (default_room_id,)
        )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            done BOOLEAN,
            list_id INTEGER NOT NULL,
            active_tags TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY(list_id) REFERENCES lists(id)
        )
        """
    )

    item_cursor = db.execute("PRAGMA table_info(items)")
    item_cols = [col[1] for col in item_cursor.fetchall()]
    if "description" not in item_cols:
        db.execute("ALTER TABLE items ADD COLUMN description TEXT DEFAULT ''")
    if "quantity" not in item_cols:
        db.execute("ALTER TABLE items ADD COLUMN quantity INTEGER DEFAULT 1")

    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_list_done_name ON items(list_id, done, name)"
    )
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lists_slug ON lists(slug)")
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_lists_room_name_nocase "
        "ON lists(room_id, name COLLATE NOCASE)"
    )
    db.commit()

    return db


db = init_database()
