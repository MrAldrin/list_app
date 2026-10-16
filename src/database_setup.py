import os
import sqlite3
import threading
import uuid
from functools import partial
from pathlib import Path
from typing import Any

from config import require_app_password
from identifiers import make_slug
from migrations import Migration, run_migrations
from password_hashing import hash_password

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


def _ensure_default_room(db: sqlite3.Connection, app_password: str) -> int:
    existing_room = db.execute("SELECT id FROM rooms WHERE name = 'Home'").fetchone()
    if existing_room:
        return existing_room[0]

    pw_hash = hash_password(app_password)
    insert = db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
        ("Home", make_slug("Home"), pw_hash),
    )
    if insert.lastrowid is None:
        raise RuntimeError("Default room insert returned no ID")
    return insert.lastrowid


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


def _migration_1_baseline(db: sqlite3.Connection, app_password: str) -> None:
    """Create the version 1 schema in an empty database.

    The statements are plain CREATEs. A database that already has these tables
    (version 0, from before versioned migrations) fails here, and the runner
    rolls everything back. Later schema changes go in new migrations.
    """
    db.execute(
        """
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            password_hash TEXT NOT NULL
        )
        """
    )
    # ALTER, not inline columns: production's stored schema was built this way.
    db.execute(
        "ALTER TABLE rooms ADD COLUMN authorization_version INTEGER NOT NULL DEFAULT 1"
    )

    db.execute(
        """
        CREATE TABLE room_access_tokens (
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
    # ALTER, not inline columns: production's stored schema was built this way.
    db.execute("ALTER TABLE lists ADD COLUMN share_token TEXT")

    db.execute(
        """
        CREATE TABLE room_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT NOT NULL UNIQUE,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            revoked_at INTEGER
        )
        """
    )

    _ensure_default_room(db, app_password)
    db.execute("CREATE UNIQUE INDEX idx_lists_share_token ON lists(share_token)")

    _create_items_table(db)
    db.execute("CREATE INDEX idx_items_list_done_name ON items(list_id, done, name)")
    db.execute("CREATE UNIQUE INDEX idx_lists_slug ON lists(slug)")
    db.execute(
        "CREATE UNIQUE INDEX idx_room_access_tokens_hash "
        "ON room_access_tokens(token_hash)"
    )
    db.execute(
        "CREATE INDEX idx_room_access_tokens_room ON room_access_tokens(room_id)"
    )
    db.execute(
        "CREATE UNIQUE INDEX idx_lists_room_name_nocase "
        "ON lists(room_id, name COLLATE NOCASE)"
    )
    db.execute(
        "CREATE UNIQUE INDEX idx_items_list_name_nocase "
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


def _migration_3_offline_ready_schema(db: sqlite3.Connection) -> None:
    """Add public uids, change counters and the deletions and op_id tables.

    Lists and items get a ``uid`` (UUID v4 string) for the JSON API, and a
    ``changed_seq`` stamped from their room's ``change_seq``.
    """
    db.execute("ALTER TABLE rooms ADD COLUMN change_seq INTEGER NOT NULL DEFAULT 0")
    for table in ("lists", "items"):
        db.execute(f"ALTER TABLE {table} ADD COLUMN uid TEXT")
        db.execute(
            f"ALTER TABLE {table} ADD COLUMN changed_seq INTEGER NOT NULL DEFAULT 0"
        )
        for (row_id,) in db.execute(f"SELECT id FROM {table}").fetchall():
            db.execute(
                f"UPDATE {table} SET uid = ? WHERE id = ?", (str(uuid.uuid4()), row_id)
            )
        db.execute(f"CREATE UNIQUE INDEX idx_{table}_uid ON {table}(uid)")

    # Deleting a room removes its rows here (foreign keys are on in the app).
    db.execute(
        """
        CREATE TABLE deletions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK (kind IN ('list', 'item')),
            uid TEXT NOT NULL,
            changed_seq INTEGER NOT NULL
        )
        """
    )
    db.execute("CREATE INDEX idx_deletions_room_seq ON deletions(room_id, changed_seq)")
    db.execute(
        """
        CREATE TABLE processed_ops (
            op_id TEXT PRIMARY KEY,
            room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
            request_hash TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL
                DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )
        """
    )
    db.execute("CREATE INDEX idx_processed_ops_created_at ON processed_ops(created_at)")


# A random UUID v4 as a lowercase string: version nibble 4, variant 8/9/a/b.
_SQL_UUID4 = (
    "lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || "
    "substr(lower(hex(randomblob(2))), 2) || '-' || "
    "substr('89ab', 1 + (random() & 3), 1) || "
    "substr(lower(hex(randomblob(2))), 2) || '-' || lower(hex(randomblob(6)))"
)
_ITEM_ROOM_ID = "(SELECT room_id FROM lists WHERE id = {row}.list_id)"
_ROOM_SEQ = "(SELECT change_seq FROM rooms WHERE id = {room_id})"

# Change tracking: see docs/change-tracking.md. The update triggers skip the
# triggers' own changed_seq stamp (WHEN guard), so they never loop, even if
# recursive triggers were turned on. A migration that rebuilds rooms, lists or
# items drops these triggers and must create them again. Migration 4 creates
# them from this dict: change a trigger only in a new migration that drops and
# recreates it.
_CHANGE_TRACKING_TRIGGERS = {
    "lists_track_insert": f"""
        AFTER INSERT ON lists
        BEGIN
            UPDATE rooms SET change_seq = change_seq + 1 WHERE id = NEW.room_id;
            UPDATE lists
            SET changed_seq = COALESCE({_ROOM_SEQ.format(room_id="NEW.room_id")},
                                       changed_seq),
                uid = COALESCE(uid, {_SQL_UUID4})
            WHERE id = NEW.id;
        END""",
    "lists_track_update": f"""
        AFTER UPDATE ON lists
        WHEN NEW.changed_seq IS OLD.changed_seq
        BEGIN
            UPDATE rooms SET change_seq = change_seq + 1 WHERE id = NEW.room_id;
            UPDATE lists
            SET changed_seq = COALESCE({_ROOM_SEQ.format(room_id="NEW.room_id")},
                                       changed_seq)
            WHERE id = NEW.id;
        END""",
    "lists_track_delete": """
        AFTER DELETE ON lists
        BEGIN
            UPDATE rooms SET change_seq = change_seq + 1 WHERE id = OLD.room_id;
            INSERT INTO deletions (room_id, kind, uid, changed_seq)
            SELECT id, 'list', OLD.uid, change_seq FROM rooms
            WHERE id = OLD.room_id AND OLD.uid IS NOT NULL;
        END""",
    "items_track_insert": f"""
        AFTER INSERT ON items
        BEGIN
            UPDATE rooms SET change_seq = change_seq + 1
            WHERE id = {_ITEM_ROOM_ID.format(row="NEW")};
            UPDATE items
            SET changed_seq = COALESCE(
                    {_ROOM_SEQ.format(room_id=_ITEM_ROOM_ID.format(row="NEW"))},
                    changed_seq),
                uid = COALESCE(uid, {_SQL_UUID4})
            WHERE id = NEW.id;
        END""",
    "items_track_update": f"""
        AFTER UPDATE ON items
        WHEN NEW.changed_seq IS OLD.changed_seq
        BEGIN
            UPDATE rooms SET change_seq = change_seq + 1
            WHERE id = {_ITEM_ROOM_ID.format(row="NEW")};
            UPDATE items
            SET changed_seq = COALESCE(
                    {_ROOM_SEQ.format(room_id=_ITEM_ROOM_ID.format(row="NEW"))},
                    changed_seq)
            WHERE id = NEW.id;
        END""",
    # An item whose list is already gone records nothing: clients drop the
    # items of a deleted list themselves.
    "items_track_delete": f"""
        AFTER DELETE ON items
        BEGIN
            UPDATE rooms SET change_seq = change_seq + 1
            WHERE id = {_ITEM_ROOM_ID.format(row="OLD")};
            INSERT INTO deletions (room_id, kind, uid, changed_seq)
            SELECT r.id, 'item', OLD.uid, r.change_seq
            FROM lists AS l JOIN rooms AS r ON r.id = l.room_id
            WHERE l.id = OLD.list_id AND OLD.uid IS NOT NULL;
        END""",
    # Only renames: password and token changes do not change room data.
    "rooms_track_rename": """
        AFTER UPDATE OF name ON rooms
        BEGIN
            UPDATE rooms SET change_seq = change_seq + 1 WHERE id = NEW.id;
        END""",
}


def _migration_4_change_tracking_triggers(db: sqlite3.Connection) -> None:
    """Bump room change_seq, stamp changed_seq, fill uids, record deletions."""
    for name, body in _CHANGE_TRACKING_TRIGGERS.items():
        db.execute(f"CREATE TRIGGER {name} {body}")


def _migration_5_positive_visibility_counts(db: sqlite3.Connection) -> None:
    """Preserve zero-count hiding with All, and require positive counters."""
    db.execute("""
        UPDATE lists SET
            hide_done_mode = CASE
                WHEN (hide_done_mode = 'age' AND hide_done_age_days = 0)
                  OR (hide_done_mode = 'recent' AND hide_done_recent_count = 0)
                THEN 'all' ELSE hide_done_mode END,
            hide_done_age_days = CASE WHEN hide_done_age_days = 0
                THEN 7 ELSE hide_done_age_days END,
            hide_done_recent_count = CASE WHEN hide_done_recent_count = 0
                THEN 10 ELSE hide_done_recent_count END
        WHERE hide_done_age_days = 0 OR hide_done_recent_count = 0
    """)
    # Add focused guards without rebuilding lists or disturbing tracking triggers.
    for action in ("INSERT", "UPDATE OF hide_done_age_days, hide_done_recent_count"):
        name = "insert" if action == "INSERT" else "update"
        db.execute(f"""
            CREATE TRIGGER lists_positive_visibility_{name}
            BEFORE {action} ON lists
            WHEN typeof(NEW.hide_done_age_days) != 'integer'
              OR NEW.hide_done_age_days NOT BETWEEN 1 AND 100000
              OR typeof(NEW.hide_done_recent_count) != 'integer'
              OR NEW.hide_done_recent_count NOT BETWEEN 1 AND 100000
            BEGIN SELECT RAISE(ABORT, 'visibility counters must be 1 to 100000'); END
        """)


def _bad_text(column: str, limit: int) -> str:
    return (
        f"typeof({column}) != 'text' OR {column} = '' OR {column} != trim({column})"
        f" OR length({column}) > {limit}"
    )


def _not_json_array(column: str) -> str:
    # CASE: json_type() fails on malformed JSON instead of returning NULL.
    return (
        f"CASE WHEN json_valid({column}) THEN json_type({column}) != 'array' ELSE 1 END"
    )


# Per table: the columns checked, and each rule as the condition of a bad row.
# `{r}` is "" for stored rows and "NEW." in the triggers. SQLite's trim() and
# lower() only know ASCII, so the Python rules stay the main ones.
_FIELD_RULES: dict[str, tuple[tuple[str, ...], dict[str, str]]] = {
    "rooms": (
        ("name", "slug", "authorization_version"),
        {
            "name": _bad_text("{r}name", 100),
            "slug": "{r}slug IS NULL OR {r}slug = ''",
            "authorization_version": (
                "typeof({r}authorization_version) != 'integer'"
                " OR {r}authorization_version < 1"
            ),
        },
    ),
    "lists": (
        ("name", "slug", "room_id", "share_token", "list_tags"),
        {
            "name": _bad_text("{r}name", 100),
            "slug": "{r}slug IS NULL OR {r}slug = ''",
            "room_id": "{r}room_id IS NULL",
            "share_token": "{r}share_token IS NULL",
            "list_tags": _not_json_array("{r}list_tags"),
        },
    ),
    "items": (
        ("name", "description", "quantity", "done", "completed_at", "active_tags"),
        {
            "name": _bad_text("{r}name", 100) + " OR {r}name != lower({r}name)",
            "description": (
                "typeof({r}description) != 'text' OR length({r}description) > 1000"
            ),
            "quantity": "typeof({r}quantity) != 'integer' OR {r}quantity < 1",
            "done": "typeof({r}done) != 'integer' OR {r}done NOT IN (0, 1)",
            "completed_at": "{r}done != 1 AND {r}completed_at IS NOT NULL",
            "active_tags": _not_json_array("{r}active_tags"),
        },
    ),
}


def _migration_6_field_constraints(db: sqlite3.Connection) -> None:
    """Make the database reject bad names, quantities, flags and tag JSON."""
    broken = []
    for table, (_columns, rules) in _FIELD_RULES.items():
        for field, rule in rules.items():
            condition = rule.format(r="")
            count = db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {condition}"
            ).fetchone()[0]
            if count:
                broken.append(f"{table}.{field}: {count}")
    if broken:
        # No guessing: a person decides how to fix the data, then deploys again.
        raise RuntimeError("Rows break field rules: " + ", ".join(broken))

    # Guards instead of CHECKs: adding a CHECK needs a table rebuild, which
    # would drop the change-tracking triggers (see migration 5).
    for table, (columns, rules) in _FIELD_RULES.items():
        condition = " OR ".join(f"({rule.format(r='NEW.')})" for rule in rules.values())
        for name, action in (
            ("insert", "INSERT"),
            ("update", f"UPDATE OF {', '.join(columns)}"),
        ):
            db.execute(f"""
                CREATE TRIGGER {table}_field_rules_{name}
                BEFORE {action} ON {table}
                WHEN {condition}
                BEGIN SELECT RAISE(ABORT, '{table}: a value breaks a field rule'); END
            """)


# The text format of created_at, the same as processed_ops (text order is time order).
_NOW_TEXT = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def _migration_7_deletion_pruning(db: sqlite3.Connection) -> None:
    """Add a creation time to deletion records and each room's pruned seq.

    Existing records get the migration time, so the first prune removes them
    90 days after the upgrade. The two delete triggers are created again to
    record the time. Nothing is rebuilt.
    """
    db.execute(
        "ALTER TABLE rooms ADD COLUMN deletions_pruned_seq INTEGER NOT NULL DEFAULT 0"
    )
    # Nullable, because ADD COLUMN cannot take a non-constant default. The
    # triggers below always set it for new records.
    db.execute("ALTER TABLE deletions ADD COLUMN created_at TEXT")
    db.execute(
        f"UPDATE deletions SET created_at = {_NOW_TEXT} WHERE created_at IS NULL"
    )
    db.execute("CREATE INDEX idx_deletions_created_at ON deletions(created_at)")
    db.execute("DROP TRIGGER lists_track_delete")
    db.execute(
        f"""
        CREATE TRIGGER lists_track_delete
        AFTER DELETE ON lists
        BEGIN
            UPDATE rooms SET change_seq = change_seq + 1 WHERE id = OLD.room_id;
            INSERT INTO deletions (room_id, kind, uid, changed_seq, created_at)
            SELECT id, 'list', OLD.uid, change_seq, {_NOW_TEXT} FROM rooms
            WHERE id = OLD.room_id AND OLD.uid IS NOT NULL;
        END
        """
    )
    db.execute("DROP TRIGGER items_track_delete")
    db.execute(
        f"""
        CREATE TRIGGER items_track_delete
        AFTER DELETE ON items
        BEGIN
            UPDATE rooms SET change_seq = change_seq + 1
            WHERE id = {_ITEM_ROOM_ID.format(row="OLD")};
            INSERT INTO deletions (room_id, kind, uid, changed_seq, created_at)
            SELECT r.id, 'item', OLD.uid, r.change_seq, {_NOW_TEXT}
            FROM lists AS l JOIN rooms AS r ON r.id = l.room_id
            WHERE l.id = OLD.list_id AND OLD.uid IS NOT NULL;
        END
        """
    )


# Append new migrations; never edit or reorder one that has been deployed.
def _migrations(app_password: str) -> list[Migration]:
    return [
        partial(_migration_1_baseline, app_password=app_password),
        _migration_2_item_ids_never_reused,
        _migration_3_offline_ready_schema,
        _migration_4_change_tracking_triggers,
        _migration_5_positive_visibility_counts,
        _migration_6_field_constraints,
        _migration_7_deletion_pruning,
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


class _LazyConnection:
    """The app's one database connection, opened on first use.

    Importing this module does not open the database. The server opens it at
    startup (`server.lifespan`); tests and scripts open it on first use. Code
    keeps writing `db.execute(...)`, as before.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Open and migrate the database once; later calls return the same connection."""
        if self._connection is None:
            with self._lock:
                if self._connection is None:
                    self._connection = init_database()
        return self._connection

    def __getattr__(self, name: str) -> Any:
        return getattr(self.connect(), name)


_lazy_db = _LazyConnection()
# A lazy stand-in for a sqlite3.Connection. Typed Any: with the Connection type,
# ty flags the `lastrowid` returns in the callers (`int | None`).
db: Any = _lazy_db


def open_database() -> sqlite3.Connection:
    """Open and migrate the database now, unless it is open already."""
    return _lazy_db.connect()
