import json
import secrets
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import cache
from typing import Literal

import bcrypt

from database_setup import db
from field_limits import MAX_NAME_LENGTH, MIN_PASSWORD_LENGTH, too_long_message
from identifiers import make_slug, token_hash
from item_visibility import parse_completion_time, validate_visibility_settings
from password_hashing import hash_password

_DB_LOCK = threading.RLock()


@contextmanager
def transaction(*, write: bool = False) -> Iterator[None]:
    """Hold the database lock and one transaction for the block.

    Commits when the block ends normally. Rolls back on any exception and
    re-raises it. Use write=True for blocks that write: it takes SQLite's write
    lock up front (BEGIN IMMEDIATE). Do not nest it; SQLite has no nested BEGIN.
    """
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield
            db.commit()
        except BaseException:
            db.rollback()
            raise


def normalize_item_name(raw: str | None) -> str:
    return (raw or "").strip().lower()


def normalize_display_name(raw: str | None) -> str:
    """Room and list names keep the user's case; only outer whitespace goes."""
    return (raw or "").strip()


def _decode_tags(raw: str | None) -> list[str]:
    """Stored list or item tags; bad JSON or a non-list reads as no tags."""
    try:
        tags = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        return []
    if not isinstance(tags, list):
        return []
    return [tag for tag in tags if isinstance(tag, str)]


def _completion_timestamp(now: datetime | None = None) -> str:
    timestamp = datetime.now(UTC) if now is None else now
    if timestamp.tzinfo is None:
        raise ValueError("Completion timestamp must include a timezone")
    return (
        timestamp.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def get_lists(room_id: int):
    with _DB_LOCK:
        rows = db.execute(
            "SELECT id, name, slug FROM lists WHERE room_id = ? ORDER BY name COLLATE NOCASE ASC",
            (room_id,),
        ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


# Share tokens are secrets.token_urlsafe(32): always 43 characters.
SHARE_TOKEN_LENGTH = 43


def _list_for_share_token_locked(token: str | None) -> tuple[int, int] | None:
    """(list_id, room_id) of the list this share token opens, or None."""
    if not token or len(token) != SHARE_TOKEN_LENGTH:
        return None
    row = db.execute(
        "SELECT id, room_id FROM lists WHERE share_token = ?", (token,)
    ).fetchone()
    return (row[0], row[1]) if row else None


class ShareLinkDenied(LookupError):
    """The share token opens no list: never issued, reset, or the list is gone."""


@contextmanager
def share_token_transaction(
    token: str | None, *, write: bool = False
) -> Iterator[tuple[int, int]]:
    """Like room_token_transaction(), for a public share token.

    Yields (room_id, list_id) of the shared list. The token is checked inside
    the transaction, so a reset blocks every later read and write with the old
    token. Raises ShareLinkDenied without a matching list. A share token never
    grants room access: callers must limit reads and writes to this list.
    """
    with transaction(write=write):
        found = _list_for_share_token_locked(token)
        if found is None:
            raise ShareLinkDenied
        list_id, room_id = found
        yield room_id, list_id


def get_share_token_locked(list_id: int) -> str:
    return db.execute(
        "SELECT share_token FROM lists WHERE id = ?", (list_id,)
    ).fetchone()[0]


def rotate_share_token_locked(list_id: int) -> str:
    """Give the list a new share token; the old link stops working at once."""
    token = secrets.token_urlsafe(32)
    db.execute("UPDATE lists SET share_token = ? WHERE id = ?", (token, list_id))
    return token


def update_list_visibility_settings_locked(
    list_id: int,
    *,
    mode: str | None = None,
    age_days: int | None = None,
    recent_count: int | None = None,
) -> None:
    """Change the given visibility settings; None keeps the stored value.

    The merge happens inside the caller's write transaction, so two devices
    changing different fields do not overwrite each other. Raises ValueError
    when the merged settings are out of range. The list must exist.
    """
    stored = db.execute(
        "SELECT hide_done_mode, hide_done_age_days, hide_done_recent_count "
        "FROM lists WHERE id = ?",
        (list_id,),
    ).fetchone()
    mode = stored[0] if mode is None else mode
    age_days = stored[1] if age_days is None else age_days
    recent_count = stored[2] if recent_count is None else recent_count
    validate_visibility_settings(mode, age_days, recent_count)
    db.execute(
        "UPDATE lists SET hide_done_mode = ?, hide_done_age_days = ?, "
        "hide_done_recent_count = ? WHERE id = ?",
        (mode, age_days, recent_count, list_id),
    )


def change_list_tag_locked(list_id: int, tag: str, *, add: bool) -> None:
    """Add or remove one list tag on the stored tags; no write if unchanged.

    Call inside a write transaction; the list must exist.
    """
    row = db.execute("SELECT list_tags FROM lists WHERE id = ?", (list_id,)).fetchone()
    list_tags = _decode_tags(row[0])

    if add:
        if tag not in list_tags:
            list_tags = sorted([*list_tags, tag], key=str.lower)
            db.execute(
                "UPDATE lists SET list_tags = ? WHERE id = ?",
                (json.dumps(list_tags), list_id),
            )
    else:
        updated_tags = [existing for existing in list_tags if existing != tag]
        if updated_tags != list_tags:
            db.execute(
                "UPDATE lists SET list_tags = ? WHERE id = ?",
                (json.dumps(updated_tags), list_id),
            )


def toggle_item_active_tag_locked(item_id: int, list_id: int, tag: str) -> bool:
    """Toggle one tag on the stored item tags; False if no such item.

    Call inside a write transaction.
    """
    row = db.execute(
        "SELECT active_tags FROM items WHERE id = ? AND list_id = ?",
        (item_id, list_id),
    ).fetchone()
    if row is None:
        return False
    active_tags = _decode_tags(row[0])
    if tag in active_tags:
        active_tags.remove(tag)
    else:
        active_tags.append(tag)
    db.execute(
        "UPDATE items SET active_tags = ? WHERE id = ? AND list_id = ?",
        (json.dumps(active_tags), item_id, list_id),
    )
    return True


def _find_list_by_name_locked(
    name: str, room_id: int, *, exclude_id: int | None = None
) -> tuple[int, str] | None:
    """Match list names ignoring case in Python; SQLite NOCASE only folds A-Z."""
    wanted = name.strip().casefold()
    rows = db.execute(
        "SELECT id, slug, name FROM lists WHERE room_id = ?", (room_id,)
    ).fetchall()
    for list_id, slug, existing_name in rows:
        if list_id != exclude_id and existing_name.strip().casefold() == wanted:
            return list_id, slug
    return None


def create_or_find_list_locked(
    name: str, room_id: int, *, uid: str | None = None
) -> tuple[int, str, bool]:
    """Create a list, or return the one with that name (ignoring case).

    Returns (list ID, slug, created). `uid` is the client's new public ID;
    None lets the trigger make one. It is not used for an existing list.
    """
    normalized_name = normalize_display_name(name)
    if not normalized_name:
        raise ValueError("List name cannot be empty")

    existing = _find_list_by_name_locked(normalized_name, room_id)
    if existing:
        return existing[0], existing[1], False

    slug = make_slug(name)
    result = db.execute(
        "INSERT INTO lists (name, slug, room_id, share_token, uid) "
        "VALUES (?, ?, ?, ?, ?)",
        (normalized_name, slug, room_id, secrets.token_urlsafe(32), uid),
    )
    return result.lastrowid, slug, True


def rename_list_if_unique_locked(list_id: int, room_id: int, new_name: str) -> bool:
    """Rename a list of the room; False (no change) if another list has the name.

    Call inside a write transaction, with a normalized, nonempty name.
    """
    if _find_list_by_name_locked(new_name, room_id, exclude_id=list_id):
        return False
    db.execute(
        "UPDATE lists SET name = ? WHERE id = ? AND room_id = ?",
        (new_name, list_id, room_id),
    )
    return True


def add_or_restore_item_locked(
    item_name: str, list_id: int, *, uid: str | None = None
) -> tuple[str, int]:
    """Add an item, uncheck a checked one, or report an active duplicate.

    Returns (status, item ID): "added", "restored" or "duplicate_active"
    (nothing written). Names match ignoring case and outer spaces. `uid` is
    the client's public ID for a new item; it is not used otherwise. Call
    inside a write transaction with a normalized, nonempty name.
    """
    existing = db.execute(
        "SELECT id, done FROM items WHERE list_id = ? "
        "AND trim(name) = ? COLLATE NOCASE",
        (list_id, item_name),
    ).fetchone()
    if existing:
        if not existing[1]:
            return "duplicate_active", existing[0]
        db.execute(
            "UPDATE items SET done = 0, completed_at = NULL WHERE id = ?",
            (existing[0],),
        )
        return "restored", existing[0]
    result = db.execute(
        "INSERT INTO items (name, done, list_id, uid) VALUES (?, 0, ?, ?)",
        (item_name, list_id, uid),
    )
    return "added", result.lastrowid


def restore_deleted_item_locked(
    list_id: int,
    name: str,
    done: bool,
    active_tags: list[str],
    description: str,
    quantity: int,
    *,
    completed_at: str | None = None,
    uid: str | None = None,
) -> int | None:
    """Insert a deleted item again as a new row; return its ID.

    None (nothing written) when an item with that name exists, ignoring case
    and outer spaces. `completed_at` is kept only when `done`. Call inside a
    write transaction.
    """
    if db.execute(
        "SELECT 1 FROM items WHERE list_id = ? AND trim(name) = ? COLLATE NOCASE",
        (list_id, name.strip()),
    ).fetchone():
        return None
    result = db.execute(
        """
        INSERT INTO items (
            name, done, list_id, active_tags, description, quantity,
            completed_at, uid
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            done,
            list_id,
            json.dumps(active_tags),
            description,
            quantity,
            completed_at if done else None,
            uid,
        ),
    )
    return result.lastrowid


def update_item_done_locked(
    item_id: int, list_id: int, done: bool, *, now: datetime | None = None
) -> bool:
    """Set the done state; False if no such item. Call in a write transaction.

    Checking sets `completed_at` unless the item is already checked;
    unchecking clears it.
    """
    if done:
        result = db.execute(
            "UPDATE items SET completed_at = CASE WHEN COALESCE(done, 0) = 0 "
            "THEN ? ELSE completed_at END, done = 1 "
            "WHERE id = ? AND list_id = ?",
            (_completion_timestamp(now), item_id, list_id),
        )
    else:
        result = db.execute(
            "UPDATE items SET done = 0, completed_at = NULL "
            "WHERE id = ? AND list_id = ?",
            (item_id, list_id),
        )
    return result.rowcount > 0


def update_item_details_locked(
    item_id: int, list_id: int, name: str, description: str, quantity: int | None
) -> Literal["saved", "duplicate", "missing"]:
    """Save name, description and quantity together, or nothing.

    "duplicate": another item of the list has the name (ignoring case and
    outer spaces). "missing": no such item. None keeps the quantity. Call
    inside a write transaction with checked values.
    """
    duplicate = db.execute(
        "SELECT id FROM items WHERE trim(name) = ? COLLATE NOCASE "
        "AND id != ? AND list_id = ?",
        (name, item_id, list_id),
    ).fetchone()
    if duplicate:
        return "duplicate"
    result = db.execute(
        "UPDATE items SET name = ?, description = ?, "
        "quantity = COALESCE(?, quantity) WHERE id = ? AND list_id = ?",
        (name, description, quantity, item_id, list_id),
    )
    return "saved" if result.rowcount > 0 else "missing"


def adjust_item_quantity_locked(item_id: int, list_id: int, delta: int) -> bool:
    """Add `delta`, never below 1 (empty counts as 1); False if no such item.

    Call inside a write transaction.
    """
    result = db.execute(
        "UPDATE items SET quantity = MAX(1, COALESCE(quantity, 1) + ?) "
        "WHERE id = ? AND list_id = ?",
        (delta, item_id, list_id),
    )
    return result.rowcount > 0


def delete_item_locked(item_id: int, list_id: int) -> bool:
    """Delete an item of the list; False if it was already gone."""
    result = db.execute(
        "DELETE FROM items WHERE id = ? AND list_id = ?", (item_id, list_id)
    )
    return result.rowcount > 0


def delete_list_locked(list_id: int) -> None:
    """Delete a list and its items; call inside a write transaction."""
    # Items first, so each item delete is recorded for its room.
    db.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
    db.execute("DELETE FROM lists WHERE id = ?", (list_id,))


def get_rooms():
    with _DB_LOCK:
        rows = db.execute(
            "SELECT id, name, slug FROM rooms ORDER BY name COLLATE NOCASE ASC"
        ).fetchall()
    return [{"id": r[0], "name": r[1], "slug": r[2]} for r in rows]


def get_room_details_by_slug(slug: str):
    with _DB_LOCK:
        row = db.execute(
            "SELECT id, name, slug FROM rooms WHERE slug = ?", (slug,)
        ).fetchone()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "slug": row[2]}


def create_room(name: str, plain_password: str):
    normalized_name = normalize_display_name(name)
    if not normalized_name:
        raise ValueError("Room name cannot be empty")
    if message := too_long_message("Room name", normalized_name, MAX_NAME_LENGTH):
        raise ValueError(message)
    check_new_room_password(plain_password)

    pw_hash = hash_password(plain_password)

    slug = make_slug(name)

    with transaction(write=True):
        result = db.execute(
            "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
            (normalized_name, slug, pw_hash),
        )
        return result.lastrowid, slug


class RoomAccessDenied(PermissionError):
    """Raised when a token cannot authorize the requested private room action."""


def _valid_room_id_for_token_locked(room_slug: str, token: str | None) -> int | None:
    if not token:
        return None
    row = db.execute(
        """
        SELECT r.id
        FROM rooms AS r
        JOIN room_access_tokens AS t ON t.room_id = r.id
        WHERE r.slug = ?
          AND t.token_hash = ?
          AND t.authorization_version = r.authorization_version
          AND t.revoked_at IS NULL
        """,
        (room_slug, token_hash(token)),
    ).fetchone()
    return row[0] if row else None


def room_matches_token_locked(room_slug: str, room_id: int, token: str | None) -> bool:
    """Whether the token authorizes this room; call inside a transaction."""
    return _valid_room_id_for_token_locked(room_slug, token) == room_id


@contextmanager
def room_token_transaction(
    room_slug: str, token: str | None, *, write: bool = False
) -> Iterator[int]:
    """Hold the database lock and one transaction; yield the authorized room ID.

    The token is checked inside the transaction, so the caller's reads or
    writes in the `with` block see the same state the check saw. Raises
    RoomAccessDenied when the token does not authorize the room. Commits when
    the block ends normally and rolls back on any exception. Use write=True
    for blocks that write (takes SQLite's write lock up front).
    """
    with transaction(write=write):
        room_id = _valid_room_id_for_token_locked(room_slug, token)
        if room_id is None:
            raise RoomAccessDenied
        yield room_id


def get_room_details_locked(room_id: int) -> dict | None:
    """Room slug and name; call inside room_token_transaction()."""
    row = db.execute("SELECT slug, name FROM rooms WHERE id = ?", (room_id,)).fetchone()
    return {"slug": row[0], "name": row[1]} if row else None


# Changes feed readers (docs/api.md, "Reading: the changes feed"). Call them in
# one room_token_transaction(), so the rows match the room seq. `since=None`
# reads every row; otherwise only rows changed after that seq.


def get_room_seq_locked(room_id: int) -> int:
    return db.execute(
        "SELECT change_seq FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]


def _since_bound(since: int | None) -> int:
    # Rows from before change tracking have changed_seq 0.
    return -1 if since is None else since


def get_list_changes_locked(
    room_id: int, since: int | None, *, list_id: int | None = None
) -> list[dict]:
    """Lists of the room changed after `since`; only `list_id` if given."""
    rows = db.execute(
        """
        SELECT uid, slug, name, list_tags, hide_done_mode, hide_done_age_days,
               hide_done_recent_count, changed_seq
        FROM lists
        WHERE room_id = :room_id AND changed_seq > :since
          AND (:list_id IS NULL OR id = :list_id)
        ORDER BY id
        """,
        {"room_id": room_id, "since": _since_bound(since), "list_id": list_id},
    ).fetchall()
    return [
        {
            "uid": row[0],
            "slug": row[1],
            "name": row[2],
            "tags": sorted(_decode_tags(row[3]), key=str.lower),
            "hide_done": {
                "mode": row[4],
                "age_days": row[5],
                "recent_count": row[6],
            },
            "changed_seq": row[7],
        }
        for row in rows
    ]


def normalize_completion_time(value: object) -> str | None:
    """A completion time as stored (UTC with Z), or None when unreadable."""
    completed_at = parse_completion_time(value)
    return None if completed_at is None else _completion_timestamp(completed_at)


def _feed_completed_at(done: bool, stored: object) -> str | None:
    """UTC with Z, or None when not done or the stored time is unreadable."""
    return normalize_completion_time(stored) if done else None


def get_item_changes_locked(
    room_id: int, since: int | None, *, list_id: int | None = None
) -> list[dict]:
    """Items of the room changed after `since`; only of `list_id` if given."""
    rows = db.execute(
        """
        SELECT i.uid, l.uid, i.name, i.done, i.completed_at, i.quantity,
               i.description, i.active_tags, i.changed_seq
        FROM items AS i
        JOIN lists AS l ON l.id = i.list_id
        WHERE l.room_id = :room_id AND i.changed_seq > :since
          AND (:list_id IS NULL OR l.id = :list_id)
        ORDER BY i.id
        """,
        {"room_id": room_id, "since": _since_bound(since), "list_id": list_id},
    ).fetchall()
    items = []
    for row in rows:
        done = bool(row[3])
        # Same defaults as get_list_data().
        items.append(
            {
                "uid": row[0],
                "list_uid": row[1],
                "name": row[2],
                "done": done,
                "completed_at": _feed_completed_at(done, row[4]),
                "quantity": row[5] if row[5] is not None else 1,
                "description": row[6] or "",
                "tags": _decode_tags(row[7]),
                "changed_seq": row[8],
            }
        )
    return items


def get_deletions_locked(room_id: int, since: int) -> list[dict]:
    rows = db.execute(
        "SELECT kind, uid FROM deletions WHERE room_id = ? AND changed_seq > ? "
        "ORDER BY changed_seq, id",
        (room_id, since),
    ).fetchall()
    return [{"kind": row[0], "uid": row[1]} for row in rows]


# API write helpers. Call them inside a room_token_transaction(write=True).


def list_id_for_uid_locked(room_id: int, list_uid: str) -> int | None:
    """The list's integer ID, or None if it is gone or in another room."""
    row = db.execute(
        "SELECT id FROM lists WHERE uid = ? AND room_id = ?", (list_uid, room_id)
    ).fetchone()
    return row[0] if row else None


def get_list_uid_locked(list_id: int) -> str:
    return db.execute("SELECT uid FROM lists WHERE id = ?", (list_id,)).fetchone()[0]


def item_id_for_uid_locked(list_id: int, item_uid: str) -> int | None:
    """The item's integer ID, or None if it is gone or in another list."""
    row = db.execute(
        "SELECT id FROM items WHERE uid = ? AND list_id = ?", (item_uid, list_id)
    ).fetchone()
    return row[0] if row else None


def get_item_uid_locked(item_id: int) -> str:
    return db.execute("SELECT uid FROM items WHERE id = ?", (item_id,)).fetchone()[0]


def uid_in_use_locked(uid: str) -> bool:
    """True if a list or item has, or had, this public ID (in any room)."""
    return (
        db.execute(
            "SELECT 1 FROM lists WHERE uid = :uid "
            "UNION ALL SELECT 1 FROM items WHERE uid = :uid "
            "UNION ALL SELECT 1 FROM deletions WHERE uid = :uid LIMIT 1",
            {"uid": uid},
        ).fetchone()
        is not None
    )


@contextmanager
def savepoint_locked() -> Iterator[None]:
    """Undo the block's writes if it raises; the outer transaction goes on."""
    db.execute("SAVEPOINT block")
    try:
        yield
    except BaseException:
        db.execute("ROLLBACK TO block")
        db.execute("RELEASE block")
        raise
    db.execute("RELEASE block")


def find_processed_op_locked(op_id: str) -> tuple[int, str, str] | None:
    """(room ID, request hash, response JSON) stored for an op_id, or None."""
    row = db.execute(
        "SELECT room_id, request_hash, response_json FROM processed_ops "
        "WHERE op_id = ?",
        (op_id,),
    ).fetchone()
    return (row[0], row[1], row[2]) if row else None


def store_processed_op_locked(
    op_id: str, room_id: int, request_hash: str, response_json: str
) -> None:
    db.execute(
        "INSERT INTO processed_ops (op_id, room_id, request_hash, response_json) "
        "VALUES (?, ?, ?, ?)",
        (op_id, room_id, request_hash, response_json),
    )


PROCESSED_OP_DAYS = 30


def prune_processed_ops(max_age_days: int = PROCESSED_OP_DAYS) -> int:
    """Delete stored op results older than `max_age_days`; return the count."""
    with transaction(write=True):
        # created_at uses the same text format, so text order is time order.
        result = db.execute(
            "DELETE FROM processed_ops WHERE created_at < "
            "strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?)",
            (f"-{int(max_age_days)} days",),
        )
        return result.rowcount


def _insert_room_access_token_locked(room_id: int, authorization_version: int) -> str:
    token = secrets.token_urlsafe(32)
    db.execute(
        """
        INSERT INTO room_access_tokens (token_hash, room_id, authorization_version)
        VALUES (?, ?, ?)
        """,
        (token_hash(token), room_id, authorization_version),
    )
    return token


def _password_matches(plain_password: str, stored_hash: object) -> bool:
    """Reject malformed/unsupported stored hashes without hiding database errors."""
    if not isinstance(stored_hash, str):
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), stored_hash.encode("utf-8")
        )
    except ValueError:
        # bcrypt rejects invalid salts/formats (and unsupported password inputs).
        return False


@cache
def _dummy_password_hash() -> str:
    """A hash with the same cost as room passwords, made once per process."""
    return hash_password("no-such-room")


def authenticate_room_and_issue_token(
    room_slug: str, plain_password: str
) -> tuple[int, str] | None:
    """Check a password and atomically create a token for the current room version."""
    # Early "return None" paths only read, so the commit at block end changes nothing.
    with transaction(write=True):
        row = db.execute(
            """
            SELECT id, password_hash, authorization_version
            FROM rooms
            WHERE slug = ?
            """,
            (room_slug,),
        ).fetchone()
        if not row:
            # Spend the same bcrypt time as a wrong password, so response
            # timing does not reveal which room slugs exist.
            _password_matches(plain_password, _dummy_password_hash())
            return None
        if not _password_matches(plain_password, row[1]):
            return None
        token = _insert_room_access_token_locked(row[0], row[2])
        return row[0], token


def revoke_room_access_token(room_slug: str, token: str) -> None:
    """Revoke a token after the browser could not persist it."""
    with transaction(write=True):
        db.execute(
            """
            UPDATE room_access_tokens
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE token_hash = ?
              AND room_id = (SELECT id FROM rooms WHERE slug = ?)
            """,
            (token_hash(token), room_slug),
        )


def _replace_room_password_locked(room_id: int, password_hash: str) -> int | None:
    row = db.execute(
        "SELECT authorization_version FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()
    if not row:
        return None

    authorization_version = row[0] + 1
    db.execute(
        """
        UPDATE rooms
        SET password_hash = ?, authorization_version = ?
        WHERE id = ?
        """,
        (password_hash, authorization_version, room_id),
    )
    # Deleting old rows avoids an unbounded accumulation after password resets.
    db.execute("DELETE FROM room_access_tokens WHERE room_id = ?", (room_id,))
    return authorization_version


def reset_room_password_by_slug(room_slug: str, new_plain_password: str) -> int | None:
    """Admin reset: set a room's password by slug and revoke all its tokens.

    Returns the room id, or None when no room has this slug (nothing changed).
    The caller checks admin sign-in and the password rules first.
    """
    check_new_room_password(new_plain_password)

    pw_hash = hash_password(new_plain_password)
    # The early "return None" happens before any write, so the commit changes nothing.
    with transaction(write=True):
        row = db.execute("SELECT id FROM rooms WHERE slug = ?", (room_slug,)).fetchone()
        if row is None or _replace_room_password_locked(row[0], pw_hash) is None:
            return None
        return row[0]


# bcrypt refuses longer passwords (bcrypt 5 raises ValueError).
MAX_PASSWORD_BYTES = 72


def check_new_room_password(new_plain_password: str) -> None:
    """The one rule for every room password that is set.

    Used by admin room creation, admin password reset, room password change and
    room creation from an invitation. Blank (only spaces), shorter than
    MIN_PASSWORD_LENGTH characters, and longer than 72 UTF-8 bytes are refused.
    The password is saved as typed. Sign-in does not apply this rule, so rooms
    with older, shorter passwords still open. Raises ValueError for the user.
    """
    if not new_plain_password.strip():
        raise ValueError("Password cannot be empty")
    if len(new_plain_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(new_plain_password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"The password cannot be longer than {MAX_PASSWORD_BYTES} bytes"
        )


def change_room_password_locked(
    room_id: int, current_plain_password: str, new_plain_password: str
) -> str | None:
    """Check the current password, set the new one, revoke every token.

    Returns a fresh token for the changing device, or None for a wrong current
    password (nothing changed). Call inside a write transaction.
    """
    row = db.execute(
        "SELECT password_hash FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()
    if not row or not _password_matches(current_plain_password, row[0]):
        return None
    new_hash = hash_password(new_plain_password)
    authorization_version = _replace_room_password_locked(room_id, new_hash)
    if authorization_version is None:
        return None
    return _insert_room_access_token_locked(room_id, authorization_version)


def delete_room_with_password_locked(room_id: int, plain_password: str) -> bool:
    """Delete the room and all its lists and items if the password matches.

    False for a wrong password (nothing changed). Call inside a write
    transaction. Tokens, deletion records and stored ops go by cascade.
    """
    row = db.execute(
        "SELECT password_hash FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()
    if not row or not _password_matches(plain_password, row[0]):
        return False
    _delete_room_rows_locked(room_id)
    return True


def _delete_room_rows_locked(room_id: int) -> None:
    """Remove a room's lists and items, then the room. The one delete rule."""
    list_rows = db.execute(
        "SELECT id FROM lists WHERE room_id = ?", (room_id,)
    ).fetchall()
    for list_row in list_rows:
        db.execute("DELETE FROM items WHERE list_id = ?", (list_row[0],))
    db.execute("DELETE FROM lists WHERE room_id = ?", (room_id,))
    db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))


def delete_room_by_slug(room_slug: str) -> int | None:
    """Admin delete: remove a room by slug, without its password.

    Returns the room id, or None when no room has this slug (nothing changed).
    The caller checks admin sign-in first.
    """
    with transaction(write=True):
        row = db.execute("SELECT id FROM rooms WHERE slug = ?", (room_slug,)).fetchone()
        if row is None:
            return None
        _delete_room_rows_locked(row[0])
        return row[0]


def rename_room_locked(room_id: int, new_name: str) -> None:
    """Rename a room (trimmed, case kept). Call inside a write transaction."""
    new_name = normalize_display_name(new_name)
    if not new_name:
        raise ValueError("Room name cannot be empty")
    db.execute("UPDATE rooms SET name = ? WHERE id = ?", (new_name, room_id))
