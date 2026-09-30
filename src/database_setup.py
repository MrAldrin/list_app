import os
import re
import secrets
import sqlite3
import uuid
from functools import partial
from pathlib import Path

import bcrypt

from config import require_app_password
from migrations import Migration, run_migrations

_DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "list.db"
# How long a write waits for another connection's lock (e.g. a backup) before
# failing. Waiting freezes the whole app, so keep it short.
# See docs/background/sqlite-wal-timeout.md.
LOCK_WAIT_SECONDS = 1.0


def _database_path() -> str:
    return os.environ.get("DB_PATH", str(_DEFAULT_DATABASE_PATH))


def _backup_path(database_path: str) -> Path | None:
    """Where to keep the pre-migration copy; None for in-memory databases."""
    if configured := os.environ.get("DB_BACKUP_PATH"):
        return Path(configured)
    if database_path == ":memory:":
        return None
    path = Path(database_path)
    return path.with_name(f"{path.stem}-pre-migration{path.suffix}")


def _create_slug(name: str) -> str:
    safe_name = re.sub(r"[^a-z0-9]", "-", name.lower().strip())
    short_uuid = str(uuid.uuid4())[:6]
    return f"{safe_name}-{short_uuid}"


def _ensure_default_room(db: sqlite3.Connection, app_password: str) -> int:
    existing_room = db.execute("SELECT id FROM rooms WHERE name = 'Home'").fetchone()
    if existing_room:
        return existing_room[0]

    pw_hash = bcrypt.hashpw(app_password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )
    insert = db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
        ("Home", _create_slug("Home"), pw_hash),
    )
    if insert.lastrowid is None:
        raise RuntimeError("Default room insert returned no ID")
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
            room_id INTEGER,
            hide_done_mode TEXT NOT NULL DEFAULT 'off'
                CHECK (hide_done_mode IN ('off', 'all', 'age', 'recent')),
            hide_done_age_days INTEGER NOT NULL DEFAULT 7
                CHECK (hide_done_age_days >= 0),
            hide_done_recent_count INTEGER NOT NULL DEFAULT 10
                CHECK (hide_done_recent_count >= 0)
        )
        """
    )
    db.execute(
        """
        INSERT INTO lists (
            id, name, list_tags, slug, room_id, hide_done_mode,
            hide_done_age_days, hide_done_recent_count
        )
        SELECT id, name, list_tags, slug, room_id, hide_done_mode,
               hide_done_age_days, hide_done_recent_count
        FROM lists_old
        """
    )
    db.execute("DROP TABLE lists_old")


def _create_items_table(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            done BOOLEAN,
            list_id INTEGER NOT NULL,
            active_tags TEXT NOT NULL DEFAULT '[]',
            completed_at TEXT,
            FOREIGN KEY(list_id) REFERENCES lists(id)
        )
        """
    )


def _items_foreign_key_is_correct(db: sqlite3.Connection) -> bool:
    foreign_keys = db.execute("PRAGMA foreign_key_list(items)").fetchall()
    return len(foreign_keys) == 1 and (
        foreign_keys[0][2],
        foreign_keys[0][3],
        foreign_keys[0][4],
    ) == ("lists", "list_id", "id")


def _migrate_items_foreign_key(db: sqlite3.Connection) -> None:
    if _items_foreign_key_is_correct(db):
        return

    orphan = db.execute(
        """
        SELECT 1
        FROM items AS i
        LEFT JOIN lists AS l ON l.id = i.list_id
        WHERE l.id IS NULL
        LIMIT 1
        """
    ).fetchone()
    if orphan:
        raise sqlite3.IntegrityError(
            "Cannot repair items foreign key: an item references a missing list"
        )

    # Drop the known index before renaming the table so it can be recreated for
    # the replacement table instead of remaining attached to items_old.
    db.execute("DROP INDEX IF EXISTS idx_items_list_done_name")
    db.execute("ALTER TABLE items RENAME TO items_old")
    _create_items_table(db)
    db.execute(
        """
        INSERT INTO items (
            id, name, description, quantity, done, list_id, active_tags,
            completed_at
        )
        SELECT id, name, description, quantity, done, list_id, active_tags,
               completed_at
        FROM items_old
        """
    )
    db.execute("DROP TABLE items_old")


def _migration_1_baseline(db: sqlite3.Connection, app_password: str) -> None:
    """Bring fresh and pre-versioning databases to the version 1 schema.

    Every step checks the current schema first, so it is safe on any legacy
    database. Add later schema changes as new migrations, not here.
    """
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

    room_columns = [
        column[1] for column in db.execute("PRAGMA table_info(rooms)").fetchall()
    ]
    if "authorization_version" not in room_columns:
        db.execute(
            "ALTER TABLE rooms ADD COLUMN authorization_version INTEGER NOT NULL DEFAULT 1"
        )
    db.execute(
        "UPDATE rooms SET authorization_version = 1 WHERE authorization_version IS NULL"
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS room_access_tokens (
            id INTEGER PRIMARY KEY,
            token_hash TEXT NOT NULL,
            room_id INTEGER NOT NULL,
            authorization_version INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            revoked_at TEXT,
            FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
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
            room_id INTEGER,
            hide_done_mode TEXT NOT NULL DEFAULT 'off'
                CHECK (hide_done_mode IN ('off', 'all', 'age', 'recent')),
            hide_done_age_days INTEGER NOT NULL DEFAULT 7
                CHECK (hide_done_age_days >= 0),
            hide_done_recent_count INTEGER NOT NULL DEFAULT 10
                CHECK (hide_done_recent_count >= 0)
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS room_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT NOT NULL UNIQUE,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            revoked_at INTEGER
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

    list_columns = {row[1] for row in db.execute("PRAGMA table_info(lists)")}
    if "hide_done_mode" not in list_columns:
        db.execute(
            "ALTER TABLE lists ADD COLUMN hide_done_mode TEXT NOT NULL DEFAULT 'off' "
            "CHECK (hide_done_mode IN ('off', 'all', 'age', 'recent'))"
        )
    if "hide_done_age_days" not in list_columns:
        db.execute(
            "ALTER TABLE lists ADD COLUMN hide_done_age_days INTEGER NOT NULL "
            "DEFAULT 7 CHECK (hide_done_age_days >= 0)"
        )
    if "hide_done_recent_count" not in list_columns:
        db.execute(
            "ALTER TABLE lists ADD COLUMN hide_done_recent_count INTEGER NOT NULL "
            "DEFAULT 10 CHECK (hide_done_recent_count >= 0)"
        )

    default_room_id = _ensure_default_room(db, app_password)
    db.execute("UPDATE lists SET room_id = ? WHERE room_id IS NULL", (default_room_id,))

    if _lists_name_is_globally_unique(db):
        _migrate_lists_to_room_scoped_names(db)
        db.execute(
            "UPDATE lists SET room_id = ? WHERE room_id IS NULL", (default_room_id,)
        )

    # Add tokens after legacy list-table rebuilds. Existing tokens survive restarts.
    list_columns = {row[1] for row in db.execute("PRAGMA table_info(lists)")}
    if "share_token" not in list_columns:
        db.execute("ALTER TABLE lists ADD COLUMN share_token TEXT")
    for (list_id,) in db.execute(
        "SELECT id FROM lists WHERE share_token IS NULL"
    ).fetchall():
        db.execute(
            "UPDATE lists SET share_token = ? WHERE id = ?",
            (secrets.token_urlsafe(32), list_id),
        )
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_lists_share_token ON lists(share_token)"
    )

    if not db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'items'"
    ).fetchone():
        _create_items_table(db)

    item_cursor = db.execute("PRAGMA table_info(items)")
    item_cols = [col[1] for col in item_cursor.fetchall()]
    if "description" not in item_cols:
        db.execute("ALTER TABLE items ADD COLUMN description TEXT DEFAULT ''")
    if "quantity" not in item_cols:
        db.execute("ALTER TABLE items ADD COLUMN quantity INTEGER DEFAULT 1")
    if "completed_at" not in item_cols:
        db.execute("ALTER TABLE items ADD COLUMN completed_at TEXT")

    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_list_done_name ON items(list_id, done, name)"
    )
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lists_slug ON lists(slug)")
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_room_access_tokens_hash "
        "ON room_access_tokens(token_hash)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_room_access_tokens_room "
        "ON room_access_tokens(room_id)"
    )
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_lists_room_name_nocase "
        "ON lists(room_id, name COLLATE NOCASE)"
    )
    _migrate_items_foreign_key(db)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_list_done_name "
        "ON items(list_id, done, name)"
    )
    duplicates = db.execute(
        "SELECT list_id, trim(name), COUNT(*) FROM items "
        "WHERE name IS NOT NULL AND trim(name) != '' "
        "GROUP BY list_id, trim(name) COLLATE NOCASE HAVING COUNT(*) > 1"
    ).fetchall()
    if duplicates:
        raise sqlite3.IntegrityError(
            f"Cannot enforce unique item names; resolve duplicates first: {duplicates}"
        )
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_items_list_name_nocase "
        "ON items(list_id, trim(name) COLLATE NOCASE) "
        "WHERE name IS NOT NULL AND trim(name) != ''"
    )


def _migration_2_item_ids_never_reused(db: sqlite3.Connection) -> None:
    """Rebuild items with AUTOINCREMENT so a deleted item's ID is never reused.

    Without it, SQLite gives a new row the highest ID + 1, so deleting the
    newest item lets a stale page's actions hit the next new item.
    """
    index_sql = [
        row[0]
        for row in db.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = 'items' AND sql IS NOT NULL"
        )
    ]
    # Nothing references items, so renaming the new table into place is safe.
    db.execute(
        """
        CREATE TABLE items_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            done BOOLEAN,
            list_id INTEGER NOT NULL,
            active_tags TEXT NOT NULL DEFAULT '[]',
            completed_at TEXT,
            FOREIGN KEY(list_id) REFERENCES lists(id)
        )
        """
    )
    db.execute(
        """
        INSERT INTO items_new (
            id, name, description, quantity, done, list_id, active_tags,
            completed_at
        )
        SELECT id, name, description, quantity, done, list_id, active_tags,
               completed_at
        FROM items
        """
    )
    db.execute("DROP TABLE items")
    db.execute("ALTER TABLE items_new RENAME TO items")
    for sql in index_sql:
        db.execute(sql)


# Append new migrations; never edit or reorder one that has been deployed.
def _migrations(app_password: str) -> list[Migration]:
    return [
        partial(_migration_1_baseline, app_password=app_password),
        _migration_2_item_ids_never_reused,
    ]


def init_database():
    app_password = require_app_password()
    database_path = _database_path()
    db = sqlite3.connect(
        database_path, check_same_thread=False, timeout=LOCK_WAIT_SECONDS
    )
    try:
        run_migrations(db, _migrations(app_password), _backup_path(database_path))
    except BaseException:
        db.close()
        raise
    return db


db = init_database()
