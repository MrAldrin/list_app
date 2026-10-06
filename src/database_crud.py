import hashlib
import json
import re
import secrets
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Literal

import bcrypt

from database_setup import db
from item_visibility import parse_completion_time, validate_visibility_settings

_DB_LOCK = threading.RLock()


class ListUnavailable(LookupError):
    """Raised when a mutation targets a list that no longer exists."""


def _require_list_identity_locked(list_id: int, expected_slug: str | None) -> None:
    """Check identity inside a write transaction; SQLite can reuse numeric IDs.

    UI callbacks pass the private slug or 'share:' plus the public token.
    Public tokens are rechecked inside the write transaction, including undo.
    None preserves ID-only calls for immediate, non-page database operations.
    """
    row = db.execute(
        "SELECT slug, share_token FROM lists WHERE id = ?", (list_id,)
    ).fetchone()
    valid = row is not None and (
        expected_slug is None
        or list_identity_matches({"slug": row[0], "share_token": row[1]}, expected_slug)
    )
    if not valid:
        raise ListUnavailable(f"List {list_id} is no longer available")


def _begin_list_write_locked(list_id: int, expected_slug: str | None) -> None:
    db.execute("BEGIN IMMEDIATE")
    _require_list_identity_locked(list_id, expected_slug)


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


def get_list_details(list_id: int):
    with _DB_LOCK:
        row = db.execute(
            """
            SELECT l.id, l.name, l.list_tags, l.slug, l.room_id, r.slug, l.share_token,
                   l.hide_done_mode, l.hide_done_age_days, l.hide_done_recent_count
            FROM lists l
            JOIN rooms r ON l.room_id = r.id
            WHERE l.id = ?
            """,
            (list_id,),
        ).fetchone()
    if not row:
        return None
    list_tags = _decode_tags(row[2])
    return {
        "id": row[0],
        "name": row[1],
        "list_tags": list_tags,
        "slug": row[3],
        "room_id": row[4],
        "room_slug": row[5],
        "share_token": row[6],
        "hide_done_mode": row[7],
        "hide_done_age_days": row[8],
        "hide_done_recent_count": row[9],
    }


def get_list_details_by_slug(slug: str):
    with _DB_LOCK:
        row = db.execute(
            """
            SELECT l.id, l.name, l.list_tags, l.slug, l.room_id, r.slug,
                   l.hide_done_mode, l.hide_done_age_days, l.hide_done_recent_count
            FROM lists l
            JOIN rooms r ON l.room_id = r.id
            WHERE l.slug = ?
            """,
            (slug,),
        ).fetchone()
    if not row:
        return None
    list_tags = _decode_tags(row[2])
    return {
        "id": row[0],
        "name": row[1],
        "list_tags": list_tags,
        "slug": row[3],
        "room_id": row[4],
        "room_slug": row[5],
        "hide_done_mode": row[6],
        "hide_done_age_days": row[7],
        "hide_done_recent_count": row[8],
    }


def list_identity_matches(details: dict, identity: str) -> bool:
    if identity.startswith("share:"):
        return details.get("share_token") == identity.removeprefix("share:")
    return details["slug"] == identity


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


def get_list_details_by_share_token(token: str):
    with _DB_LOCK:
        found = _list_for_share_token_locked(token)
        return get_list_details(found[0]) if found else None


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
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            found = _list_for_share_token_locked(token)
            if found is None:
                raise ShareLinkDenied
            list_id, room_id = found
            yield room_id, list_id
            db.commit()
        except BaseException:
            db.rollback()
            raise


def get_share_token_locked(list_id: int) -> str:
    return db.execute(
        "SELECT share_token FROM lists WHERE id = ?", (list_id,)
    ).fetchone()[0]


def rotate_share_token_locked(list_id: int) -> str:
    """Give the list a new share token; the old link stops working at once."""
    token = secrets.token_urlsafe(32)
    db.execute("UPDATE lists SET share_token = ? WHERE id = ?", (token, list_id))
    return token


def get_list_details_by_identity(identity: str):
    if identity.startswith("share:"):
        return get_list_details_by_share_token(identity.removeprefix("share:"))
    with _DB_LOCK:
        details = get_list_details_by_slug(identity)
        return get_list_details(details["id"]) if details else None


def rotate_list_share_token(
    room_slug: str, room_token: str, list_id: int, *, expected_slug: str
) -> str:
    """Only current room authorization can reset sharing; check atomically."""
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            room_id = _valid_room_id_for_token_locked(room_slug, room_token)
            row = db.execute(
                "SELECT room_id FROM lists WHERE id = ?", (list_id,)
            ).fetchone()
            if room_id is None or row is None or row[0] != room_id:
                raise PermissionError("Room access required")
            _require_list_identity_locked(list_id, expected_slug)
            token = rotate_share_token_locked(list_id)
            db.commit()
            return token
        except Exception:
            db.rollback()
            raise


def update_list_visibility_settings(
    list_id: int,
    *,
    mode: str,
    age_days: int,
    recent_count: int,
    expected_slug: str | None = None,
) -> None:
    """Atomically replace a list's checked-item visibility settings."""
    validate_visibility_settings(mode, age_days, recent_count)
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            update_list_visibility_settings_locked(
                list_id, mode=mode, age_days=age_days, recent_count=recent_count
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


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


def update_list_tags_settings(
    list_id: int, list_tags: list[str], *, expected_slug: str | None = None
):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute(
                "UPDATE lists SET list_tags = ? WHERE id = ?",
                (json.dumps(list_tags), list_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def _change_list_tag(
    list_id: int, tag: str, *, add: bool, expected_slug: str | None
) -> None:
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            change_list_tag_locked(list_id, tag, add=add)
            db.commit()
        except Exception:
            db.rollback()
            raise


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


def add_list_tag(list_id: int, tag: str, *, expected_slug: str | None = None) -> None:
    """Add one list tag without replacing tags added by another page."""
    _change_list_tag(list_id, tag, add=True, expected_slug=expected_slug)


def remove_list_tag(
    list_id: int, tag: str, *, expected_slug: str | None = None
) -> None:
    """Remove one list tag without replacing unrelated tags added by another page."""
    _change_list_tag(list_id, tag, add=False, expected_slug=expected_slug)


def update_item_active_tags(
    item_id: int,
    list_id: int,
    active_tags: list[str],
    *,
    expected_slug: str | None = None,
):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute(
                "UPDATE items SET active_tags = ? WHERE id = ? AND list_id = ?",
                (json.dumps(active_tags), item_id, list_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def toggle_item_active_tag(
    item_id: int,
    list_id: int,
    tag: str,
    *,
    expected_slug: str | None = None,
):
    """Toggle one tag on the persisted item state in a write transaction."""
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            # A stale item matches no row and changes nothing.
            toggle_item_active_tag_locked(item_id, list_id, tag)
            db.commit()
        except Exception:
            db.rollback()
            raise


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


def find_list_by_name(name: str, room_id: int):
    with _DB_LOCK:
        found = _find_list_by_name_locked(name, room_id)
    return None if found is None else (found[0],)


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

    safe_name = re.sub(r"[^a-z0-9]", "-", name.lower().strip())
    short_uuid = str(uuid.uuid4())[:6]
    slug = f"{safe_name}-{short_uuid}"
    result = db.execute(
        "INSERT INTO lists (name, slug, room_id, share_token, uid) "
        "VALUES (?, ?, ?, ?, ?)",
        (normalized_name, slug, room_id, secrets.token_urlsafe(32), uid),
    )
    return result.lastrowid, slug, True


def _create_list_locked(name: str, room_id: int) -> tuple[int, str]:
    list_id, slug, _ = create_or_find_list_locked(name, room_id)
    return list_id, slug


def create_list(name: str, room_id: int):
    with _DB_LOCK:
        try:
            list_id, slug = _create_list_locked(name, room_id)
            db.commit()
            return list_id, slug
        except Exception:
            db.rollback()
            raise


def rename_list(list_id: int, new_name: str, *, expected_slug: str | None = None):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute("UPDATE lists SET name = ? WHERE id = ?", (new_name, list_id))
            db.commit()
        except Exception:
            db.rollback()
            raise


def rename_list_if_unique(
    list_id: int,
    room_id: int,
    new_name: str,
    *,
    expected_slug: str | None = None,
) -> bool:
    """Rename a room list unless another list already uses its name."""
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            belongs_to_room = db.execute(
                "SELECT 1 FROM lists WHERE id = ? AND room_id = ?",
                (list_id, room_id),
            ).fetchone()
            if not belongs_to_room:
                raise ListUnavailable(f"List {list_id} is no longer available")

            if not rename_list_if_unique_locked(list_id, room_id, new_name):
                db.rollback()
                return False
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


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


def get_item_count(list_id: int) -> int:
    with _DB_LOCK:
        row = db.execute(
            "SELECT COUNT(*) FROM items WHERE list_id = ?", (list_id,)
        ).fetchone()
    return row[0]


def get_list_data(list_id: int):
    with _DB_LOCK:
        rows = db.execute(
            (
                "SELECT id, name, done, active_tags, description, quantity, completed_at "
                "FROM items WHERE list_id = ? "
                "ORDER BY done ASC, name COLLATE NOCASE ASC"
            ),
            (list_id,),
        ).fetchall()

    list_items = []
    for r in rows:
        active_tags = _decode_tags(r[3])
        list_items.append(
            {
                "id": r[0],
                "name": r[1],
                "done": bool(r[2]),
                "active_tags": active_tags,
                "description": r[4] or "",
                "quantity": r[5] if r[5] is not None else 1,
                "completed_at": r[6],
            }
        )

    list_history_names = sorted({item["name"] for item in list_items})
    return list_items, list_history_names


def find_item_by_name(list_id: int, item_name: str):
    with _DB_LOCK:
        result = db.execute(
            "SELECT id, done FROM items WHERE trim(name) = ? COLLATE NOCASE AND list_id = ?",
            (item_name, list_id),
        )
        return result.fetchone()


def add_or_restore_item_atomic(
    item_name: str, list_id: int, *, expected_slug: str | None = None
) -> str:
    """Add, uncheck, or reject an active item in a single write transaction."""
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            result, _ = add_or_restore_item_locked(item_name, list_id)
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise


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


def restore_item(item_id: int, list_id: int, *, expected_slug: str | None = None):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute(
                "UPDATE items SET done = 0, completed_at = NULL "
                "WHERE id = ? AND list_id = ?",
                (item_id, list_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def add_item(item_name: str, list_id: int, *, expected_slug: str | None = None):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute(
                "INSERT INTO items (name, done, list_id) VALUES (?, ?, ?)",
                (item_name, False, list_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def restore_deleted_item(
    list_id: int,
    name: str,
    done: bool,
    active_tags: list[str],
    description: str,
    quantity: int,
    *,
    completed_at: str | None = None,
    expected_slug: str | None = None,
) -> bool:
    """Restore a deleted item with all fields, unless its name is now taken."""
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            item_id = restore_deleted_item_locked(
                list_id,
                name,
                done,
                active_tags,
                description,
                quantity,
                completed_at=completed_at,
            )
            db.commit()
            return item_id is not None
        except Exception:
            db.rollback()
            raise


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


def add_item_with_state(
    item_name: str,
    list_id: int,
    done: bool,
    active_tags: list[str],
    *,
    expected_slug: str | None = None,
    now: datetime | None = None,
):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            completed_at = _completion_timestamp(now) if done else None
            db.execute(
                """
                INSERT INTO items (
                    name, done, list_id, active_tags, completed_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (item_name, done, list_id, json.dumps(active_tags), completed_at),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def update_item_done(
    item_id: int,
    list_id: int,
    done: bool,
    *,
    expected_slug: str | None = None,
    now: datetime | None = None,
):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            update_item_done_locked(item_id, list_id, done, now=now)
            db.commit()
        except Exception:
            db.rollback()
            raise


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


def find_duplicate_name(list_id: int, item_id: int, new_name: str):
    with _DB_LOCK:
        result = db.execute(
            "SELECT id FROM items WHERE trim(name) = ? COLLATE NOCASE AND id != ? AND list_id = ?",
            (new_name, item_id, list_id),
        )
        return result.fetchone()


def rename_item(
    item_id: int, list_id: int, new_name: str, *, expected_slug: str | None = None
):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute(
                "UPDATE items SET name = ? WHERE id = ? AND list_id = ?",
                (new_name, item_id, list_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def rename_item_if_unique(
    item_id: int, list_id: int, new_name: str, *, expected_slug: str | None = None
) -> bool:
    """Rename an item unless another item in the list already has that name."""
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            duplicate = db.execute(
                "SELECT id FROM items WHERE trim(name) = ? COLLATE NOCASE "
                "AND id != ? AND list_id = ?",
                (new_name, item_id, list_id),
            ).fetchone()
            if duplicate:
                db.rollback()
                return False
            db.execute(
                "UPDATE items SET name = ? WHERE id = ? AND list_id = ?",
                (new_name, item_id, list_id),
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


def update_item_details(
    item_id: int,
    list_id: int,
    name: str,
    description: str,
    quantity: int | None = None,
    *,
    expected_slug: str | None = None,
) -> bool:
    """Save an item edit in one transaction; return False on a duplicate name.

    The duplicate check runs inside the write transaction, so no field changes
    when another item already uses the name. None leaves the quantity unchanged.
    """
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            status = update_item_details_locked(
                item_id, list_id, name, description, quantity
            )
            db.commit()
            # A stale item matches no row and changes nothing.
            return status != "duplicate"
        except Exception:
            db.rollback()
            raise


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


def update_item_quantity(
    item_id: int, list_id: int, quantity: int, *, expected_slug: str | None = None
):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute(
                "UPDATE items SET quantity = ? WHERE id = ? AND list_id = ?",
                (quantity, item_id, list_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def adjust_item_quantity(
    item_id: int, list_id: int, delta: int, *, expected_slug: str | None = None
):
    """Apply a delta to the stored quantity, never to a stale UI snapshot."""
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            adjust_item_quantity_locked(item_id, list_id, delta)
            db.commit()
        except Exception:
            db.rollback()
            raise


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


def delete_item(item_id: int, list_id: int, *, expected_slug: str | None = None):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            delete_item_locked(item_id, list_id)
            db.commit()
        except Exception:
            db.rollback()
            raise


def delete_item_locked(item_id: int, list_id: int) -> bool:
    """Delete an item of the list; False if it was already gone."""
    result = db.execute(
        "DELETE FROM items WHERE id = ? AND list_id = ?", (item_id, list_id)
    )
    return result.rowcount > 0


def delete_list(list_id: int, *, expected_slug: str | None = None):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            delete_list_locked(list_id)
            db.commit()
        except Exception:
            db.rollback()
            raise


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
    if not plain_password:
        raise ValueError("Password cannot be empty")

    pw_hash = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )

    safe_name = re.sub(r"[^a-z0-9]", "-", name.lower().strip())
    short_uuid = str(uuid.uuid4())[:6]
    slug = f"{safe_name}-{short_uuid}"

    with _DB_LOCK:
        try:
            result = db.execute(
                "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
                (normalized_name, slug, pw_hash),
            )
            db.commit()
            return result.lastrowid, slug
        except Exception:
            db.rollback()
            raise


class RoomAccessDenied(PermissionError):
    """Raised when a token cannot authorize the requested private room action."""


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
        (room_slug, _token_hash(token)),
    ).fetchone()
    return row[0] if row else None


def room_matches_token_locked(room_slug: str, room_id: int, token: str | None) -> bool:
    """Whether the token authorizes this room; call inside a transaction."""
    return _valid_room_id_for_token_locked(room_slug, token) == room_id


def validate_room_access_token(room_slug: str, token: str | None) -> int | None:
    """Return the associated room ID only when the token currently authorizes it."""
    with _DB_LOCK:
        return _valid_room_id_for_token_locked(room_slug, token)


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
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            room_id = _valid_room_id_for_token_locked(room_slug, token)
            if room_id is None:
                raise RoomAccessDenied
            yield room_id
            db.commit()
        except BaseException:
            db.rollback()
            raise


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
        # Same defaults as get_list_data(), which NiceGUI renders.
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
    with _DB_LOCK:
        try:
            # created_at uses the same text format, so text order is time order.
            result = db.execute(
                "DELETE FROM processed_ops WHERE created_at < "
                "strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?)",
                (f"-{int(max_age_days)} days",),
            )
            db.commit()
            return result.rowcount
        except Exception:
            db.rollback()
            raise


def _insert_room_access_token_locked(room_id: int, authorization_version: int) -> str:
    token = secrets.token_urlsafe(32)
    db.execute(
        """
        INSERT INTO room_access_tokens (token_hash, room_id, authorization_version)
        VALUES (?, ?, ?)
        """,
        (_token_hash(token), room_id, authorization_version),
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


def authenticate_room_and_issue_token(
    room_slug: str, plain_password: str
) -> tuple[int, str] | None:
    """Check a password and atomically create a token for the current room version."""
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT id, password_hash, authorization_version
                FROM rooms
                WHERE slug = ?
                """,
                (room_slug,),
            ).fetchone()
            if not row or not _password_matches(plain_password, row[1]):
                db.rollback()
                return None
            token = _insert_room_access_token_locked(row[0], row[2])
            db.commit()
            return row[0], token
        except Exception:
            db.rollback()
            raise


def revoke_room_access_token(room_slug: str, token: str) -> None:
    """Revoke a token after the browser could not persist it."""
    with _DB_LOCK:
        try:
            db.execute(
                """
                UPDATE room_access_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE token_hash = ?
                  AND room_id = (SELECT id FROM rooms WHERE slug = ?)
                """,
                (_token_hash(token), room_slug),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def verify_room(room_slug: str, plain_password: str):
    with _DB_LOCK:
        row = db.execute(
            "SELECT id, password_hash FROM rooms WHERE slug = ?", (room_slug,)
        ).fetchone()
    if not row:
        return None

    room_id, pw_hash = row
    if _password_matches(plain_password, pw_hash):
        return room_id
    return None


def _replace_room_password_locked(
    room_id: int, password_hash: str, expected_slug: str | None = None
) -> int | None:
    row = db.execute(
        "SELECT authorization_version, slug FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()
    if not row or (expected_slug is not None and row[1] != expected_slug):
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


def update_room_password(
    room_id: int,
    new_plain_password: str,
    *,
    expected_slug: str | None = None,
) -> bool:
    """Reset a room password, returning false if its expected identity is stale."""
    if not new_plain_password:
        raise ValueError("Password cannot be empty")

    pw_hash = bcrypt.hashpw(
        new_plain_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            authorization_version = _replace_room_password_locked(
                room_id, pw_hash, expected_slug
            )
            db.commit()
            return authorization_version is not None
        except Exception:
            db.rollback()
            raise


def reset_room_password_by_slug(room_slug: str, new_plain_password: str) -> int | None:
    """Admin reset: set a room's password by slug and revoke all its tokens.

    Returns the room id, or None when no room has this slug (nothing changed).
    The caller checks admin sign-in and the password rules first.
    """
    if not new_plain_password:
        raise ValueError("Password cannot be empty")

    pw_hash = bcrypt.hashpw(
        new_plain_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM rooms WHERE slug = ?", (room_slug,)
            ).fetchone()
            if row is None or _replace_room_password_locked(row[0], pw_hash) is None:
                db.rollback()
                return None
            db.commit()
            return row[0]
        except Exception:
            db.rollback()
            raise


def change_room_password_and_issue_token(
    room_slug: str, current_plain_password: str, new_plain_password: str
) -> tuple[int, str] | None:
    """Change a password and issue the changing device a token in one transaction."""
    if not new_plain_password:
        raise ValueError("Password cannot be empty")

    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM rooms WHERE slug = ?", (room_slug,)
            ).fetchone()
            token = (
                change_room_password_locked(
                    row[0], current_plain_password, new_plain_password
                )
                if row
                else None
            )
            if token is None:
                db.rollback()
                return None
            db.commit()
            return row[0], token
        except Exception:
            db.rollback()
            raise


# bcrypt refuses longer passwords (bcrypt 5 raises ValueError).
MAX_PASSWORD_BYTES = 72


def check_new_room_password(new_plain_password: str) -> None:
    """The rules for a new room password, as NiceGUI's change dialog has them.

    Blank (only spaces) is refused; the password is saved as typed. Raises
    ValueError with a message for the user.
    """
    if not new_plain_password.strip():
        raise ValueError("New password cannot be empty")
    check_password_length(new_plain_password)


def check_password_length(plain_password: str) -> None:
    """Refuse a password bcrypt cannot hash, with a message for the user."""
    if len(plain_password.encode("utf-8")) > MAX_PASSWORD_BYTES:
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
    new_hash = bcrypt.hashpw(
        new_plain_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    authorization_version = _replace_room_password_locked(room_id, new_hash)
    if authorization_version is None:
        return None
    return _insert_room_access_token_locked(room_id, authorization_version)


def create_list_with_room_token(
    room_slug: str, token: str, name: str
) -> tuple[int, str]:
    """Create a list only if the token is still valid at the write transaction."""
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            room_id = _valid_room_id_for_token_locked(room_slug, token)
            if room_id is None:
                db.rollback()
                raise RoomAccessDenied
            list_id, slug = _create_list_locked(name, room_id)
            db.commit()
            return list_id, slug
        except Exception:
            db.rollback()
            raise


def rename_list_with_room_token(
    room_slug: str,
    token: str,
    list_id: int,
    raw_name: str | None,
    *,
    expected_slug: str | None = None,
) -> str:
    """Rename a room list while validating the token and list ownership together."""
    new_name = normalize_display_name(raw_name)
    if not new_name:
        raise ValueError("List name cannot be empty")

    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            room_id = _valid_room_id_for_token_locked(room_slug, token)
            if room_id is None:
                db.rollback()
                raise RoomAccessDenied
            belongs_to_room = db.execute(
                "SELECT 1 FROM lists WHERE id = ? AND room_id = ?",
                (list_id, room_id),
            ).fetchone()
            if not belongs_to_room:
                db.rollback()
                raise RoomAccessDenied
            _require_list_identity_locked(list_id, expected_slug)
            if not rename_list_if_unique_locked(list_id, room_id, new_name):
                db.rollback()
                raise ValueError("A list with that name already exists in this room")
            db.commit()
            return new_name
        except Exception:
            db.rollback()
            raise


def delete_list_with_room_token(
    room_slug: str, token: str, list_id: int, *, expected_slug: str | None = None
) -> None:
    """Delete a list only if it belongs to the token's currently authorized room."""
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            room_id = _valid_room_id_for_token_locked(room_slug, token)
            if room_id is None:
                db.rollback()
                raise RoomAccessDenied
            belongs_to_room = db.execute(
                "SELECT 1 FROM lists WHERE id = ? AND room_id = ?",
                (list_id, room_id),
            ).fetchone()
            if not belongs_to_room:
                list_exists = db.execute(
                    "SELECT 1 FROM lists WHERE id = ?", (list_id,)
                ).fetchone()
                db.rollback()
                if not list_exists:
                    raise ListUnavailable(f"List {list_id} is no longer available")
                raise RoomAccessDenied
            _require_list_identity_locked(list_id, expected_slug)
            delete_list_locked(list_id)
            db.commit()
        except Exception:
            db.rollback()
            raise


def rename_room_with_room_token(room_slug: str, token: str, new_name: str) -> None:
    """Rename only the room associated with a still-valid token."""
    new_name = normalize_display_name(new_name)
    if not new_name:
        raise ValueError("Room name cannot be empty")

    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            room_id = _valid_room_id_for_token_locked(room_slug, token)
            if room_id is None:
                db.rollback()
                raise RoomAccessDenied
            rename_room_locked(room_id, new_name)
            db.commit()
        except Exception:
            db.rollback()
            raise


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
    list_rows = db.execute(
        "SELECT id FROM lists WHERE room_id = ?", (room_id,)
    ).fetchall()
    for list_row in list_rows:
        db.execute("DELETE FROM items WHERE list_id = ?", (list_row[0],))
    db.execute("DELETE FROM lists WHERE room_id = ?", (room_id,))
    db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
    return True


def delete_room_with_password(room_slug: str, plain_password: str) -> bool:
    """Confirm the current password and delete the room in one transaction."""
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM rooms WHERE slug = ?", (room_slug,)
            ).fetchone()
            if not row or not delete_room_with_password_locked(row[0], plain_password):
                db.rollback()
                return False
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


def rename_room_locked(room_id: int, new_name: str) -> None:
    """Rename a room (trimmed, case kept). Call inside a write transaction."""
    new_name = normalize_display_name(new_name)
    if not new_name:
        raise ValueError("Room name cannot be empty")
    db.execute("UPDATE rooms SET name = ? WHERE id = ?", (new_name, room_id))


def rename_room(room_id: int, new_name: str):
    new_name = normalize_display_name(new_name)
    if not new_name:
        raise ValueError("Room name cannot be empty")
    with _DB_LOCK:
        try:
            rename_room_locked(room_id, new_name)
            db.commit()
        except Exception:
            db.rollback()
            raise


def delete_room(room_id: int):
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            lists = db.execute(
                "SELECT id FROM lists WHERE room_id = ?", (room_id,)
            ).fetchall()
            for list_row in lists:
                list_id = list_row[0]
                db.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
                db.execute("DELETE FROM lists WHERE id = ?", (list_id,))
            db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
            db.commit()
        except Exception:
            db.rollback()
            raise
