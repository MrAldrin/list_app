import hashlib
import json
import re
import secrets
import threading
import uuid

import bcrypt

from database_setup import db

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
            SELECT l.id, l.name, l.list_tags, l.slug, l.room_id, r.slug, l.share_token
            FROM lists l
            JOIN rooms r ON l.room_id = r.id
            WHERE l.id = ?
            """,
            (list_id,),
        ).fetchone()
    if not row:
        return None
    try:
        list_tags = json.loads(row[2]) if row[2] else []
    except json.JSONDecodeError:
        list_tags = []
    return {
        "id": row[0],
        "name": row[1],
        "list_tags": list_tags,
        "slug": row[3],
        "room_id": row[4],
        "room_slug": row[5],
        "share_token": row[6],
    }


def get_list_details_by_slug(slug: str):
    with _DB_LOCK:
        row = db.execute(
            """
            SELECT l.id, l.name, l.list_tags, l.slug, l.room_id, r.slug 
            FROM lists l
            JOIN rooms r ON l.room_id = r.id
            WHERE l.slug = ?
            """,
            (slug,),
        ).fetchone()
    if not row:
        return None
    try:
        list_tags = json.loads(row[2]) if row[2] else []
    except json.JSONDecodeError:
        list_tags = []
    return {
        "id": row[0],
        "name": row[1],
        "list_tags": list_tags,
        "slug": row[3],
        "room_id": row[4],
        "room_slug": row[5],
    }


def list_identity_matches(details: dict, identity: str) -> bool:
    if identity.startswith("share:"):
        return details.get("share_token") == identity.removeprefix("share:")
    return details["slug"] == identity


def get_list_details_by_share_token(token: str):
    if not token or len(token) != 43:
        return None
    with _DB_LOCK:
        row = db.execute(
            "SELECT id FROM lists WHERE share_token = ?", (token,)
        ).fetchone()
        return get_list_details(row[0]) if row else None


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
            token = secrets.token_urlsafe(32)
            db.execute(
                "UPDATE lists SET share_token = ? WHERE id = ?", (token, list_id)
            )
            db.commit()
            return token
        except Exception:
            db.rollback()
            raise


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


def find_list_by_name(name: str, room_id: int):
    with _DB_LOCK:
        result = db.execute(
            "SELECT id FROM lists WHERE name = ? COLLATE NOCASE AND room_id = ?",
            (name, room_id),
        )
        return result.fetchone()


def _create_list_locked(name: str, room_id: int) -> tuple[int, str]:
    normalized_name = normalize_item_name(name)
    if not normalized_name:
        raise ValueError("List name cannot be empty")

    existing = db.execute(
        "SELECT id, slug FROM lists WHERE name = ? COLLATE NOCASE AND room_id = ?",
        (normalized_name, room_id),
    ).fetchone()
    if existing:
        return existing[0], existing[1]

    safe_name = re.sub(r"[^a-z0-9]", "-", name.lower().strip())
    short_uuid = str(uuid.uuid4())[:6]
    slug = f"{safe_name}-{short_uuid}"
    result = db.execute(
        "INSERT INTO lists (name, slug, room_id, share_token) VALUES (?, ?, ?, ?)",
        (normalized_name, slug, room_id, secrets.token_urlsafe(32)),
    )
    return result.lastrowid, slug


def create_list(name: str, room_id: int):
    with _DB_LOCK:
        list_id, slug = _create_list_locked(name, room_id)
        db.commit()
        return list_id, slug


def rename_list(list_id: int, new_name: str, *, expected_slug: str | None = None):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute("UPDATE lists SET name = ? WHERE id = ?", (new_name, list_id))
            db.commit()
        except Exception:
            db.rollback()
            raise


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
                "SELECT id, name, done, active_tags, description, quantity FROM items "
                "WHERE list_id = ? ORDER BY done ASC, name COLLATE NOCASE ASC"
            ),
            (list_id,),
        ).fetchall()

    list_items = []
    for r in rows:
        try:
            active_tags = json.loads(r[3]) if r[3] else []
        except json.JSONDecodeError:
            active_tags = []
        list_items.append(
            {
                "id": r[0],
                "name": r[1],
                "done": bool(r[2]),
                "active_tags": active_tags,
                "description": r[4] or "",
                "quantity": r[5] if len(r) > 5 and r[5] is not None else 1,
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
            existing = db.execute(
                "SELECT id, done FROM items WHERE list_id = ? "
                "AND trim(name) = ? COLLATE NOCASE",
                (list_id, item_name),
            ).fetchone()
            if existing:
                if not existing[1]:
                    db.rollback()
                    return "duplicate_active"
                db.execute("UPDATE items SET done = 0 WHERE id = ?", (existing[0],))
                result = "restored"
            else:
                db.execute(
                    "INSERT INTO items (name, done, list_id) VALUES (?, 0, ?)",
                    (item_name, list_id),
                )
                result = "added"
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise


def restore_item(item_id: int, list_id: int, *, expected_slug: str | None = None):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute(
                "UPDATE items SET done = 0 WHERE id = ? AND list_id = ?",
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
    expected_slug: str | None = None,
) -> bool:
    """Restore a deleted item with all fields, unless its name is now taken."""
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            if db.execute(
                "SELECT 1 FROM items WHERE list_id = ? AND trim(name) = ? COLLATE NOCASE",
                (list_id, name.strip()),
            ).fetchone():
                db.rollback()
                return False
            db.execute(
                "INSERT INTO items (name, done, list_id, active_tags, description, quantity) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, done, list_id, json.dumps(active_tags), description, quantity),
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


def add_item_with_state(
    item_name: str,
    list_id: int,
    done: bool,
    active_tags: list[str],
    *,
    expected_slug: str | None = None,
):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute(
                "INSERT INTO items (name, done, list_id, active_tags) VALUES (?, ?, ?, ?)",
                (item_name, done, list_id, json.dumps(active_tags)),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def update_item_done(
    item_id: int, list_id: int, done: bool, *, expected_slug: str | None = None
):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute(
                "UPDATE items SET done = ? WHERE id = ? AND list_id = ?",
                (done, item_id, list_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


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
            duplicate = db.execute(
                "SELECT id FROM items WHERE trim(name) = ? COLLATE NOCASE "
                "AND id != ? AND list_id = ?",
                (name, item_id, list_id),
            ).fetchone()
            if duplicate:
                db.rollback()
                return False
            db.execute(
                "UPDATE items SET name = ?, description = ?, "
                "quantity = COALESCE(?, quantity) WHERE id = ? AND list_id = ?",
                (name, description, quantity, item_id, list_id),
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


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
            db.execute(
                "UPDATE items SET quantity = MAX(1, COALESCE(quantity, 1) + ?) "
                "WHERE id = ? AND list_id = ?",
                (delta, item_id, list_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def delete_item(item_id: int, list_id: int, *, expected_slug: str | None = None):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            db.execute(
                "DELETE FROM items WHERE id = ? AND list_id = ?",
                (item_id, list_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def delete_list(list_id: int, *, expected_slug: str | None = None):
    with _DB_LOCK:
        try:
            _begin_list_write_locked(list_id, expected_slug)
            # First delete all items in the list
            db.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
            # Then delete the list itself
            db.execute("DELETE FROM lists WHERE id = ?", (list_id,))
            db.commit()
        except Exception:
            db.rollback()
            raise


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
    normalized_name = normalize_item_name(name)
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
        result = db.execute(
            "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
            (name, slug, pw_hash),
        )
        db.commit()
        return result.lastrowid, slug


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


def validate_room_access_token(room_slug: str, token: str | None) -> int | None:
    """Return the associated room ID only when the token currently authorizes it."""
    with _DB_LOCK:
        return _valid_room_id_for_token_locked(room_slug, token)


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


def update_room_password(room_id: int, new_plain_password: str):
    """Admin password reset: atomically invalidate all current room tokens."""
    if not new_plain_password:
        raise ValueError("Password cannot be empty")

    pw_hash = bcrypt.hashpw(
        new_plain_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            _replace_room_password_locked(room_id, pw_hash)
            db.commit()
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
                """
                SELECT id, password_hash
                FROM rooms
                WHERE slug = ?
                """,
                (room_slug,),
            ).fetchone()
            if not row or not _password_matches(current_plain_password, row[1]):
                db.rollback()
                return None

            new_hash = bcrypt.hashpw(
                new_plain_password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            authorization_version = _replace_room_password_locked(row[0], new_hash)
            if authorization_version is None:
                db.rollback()
                return None
            token = _insert_room_access_token_locked(row[0], authorization_version)
            db.commit()
            return row[0], token
        except Exception:
            db.rollback()
            raise


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
    new_name = normalize_item_name(raw_name)
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
            duplicate = db.execute(
                """
                SELECT id FROM lists
                WHERE name = ? COLLATE NOCASE AND room_id = ? AND id != ?
                """,
                (new_name, room_id, list_id),
            ).fetchone()
            if duplicate:
                db.rollback()
                raise ValueError("A list with that name already exists in this room")
            db.execute("UPDATE lists SET name = ? WHERE id = ?", (new_name, list_id))
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
            db.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
            db.execute("DELETE FROM lists WHERE id = ?", (list_id,))
            db.commit()
        except Exception:
            db.rollback()
            raise


def rename_room_with_room_token(room_slug: str, token: str, new_name: str) -> None:
    """Rename only the room associated with a still-valid token."""
    if not new_name.strip():
        raise ValueError("Room name cannot be empty")

    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            room_id = _valid_room_id_for_token_locked(room_slug, token)
            if room_id is None:
                db.rollback()
                raise RoomAccessDenied
            db.execute("UPDATE rooms SET name = ? WHERE id = ?", (new_name, room_id))
            db.commit()
        except Exception:
            db.rollback()
            raise


def delete_room_with_password(room_slug: str, plain_password: str) -> bool:
    """Confirm the current password and delete the room in one transaction."""
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id, password_hash FROM rooms WHERE slug = ?", (room_slug,)
            ).fetchone()
            if not row or not _password_matches(plain_password, row[1]):
                db.rollback()
                return False
            room_id = row[0]
            list_rows = db.execute(
                "SELECT id FROM lists WHERE room_id = ?", (room_id,)
            ).fetchall()
            for list_row in list_rows:
                db.execute("DELETE FROM items WHERE list_id = ?", (list_row[0],))
            db.execute("DELETE FROM lists WHERE room_id = ?", (room_id,))
            db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


def rename_room(room_id: int, new_name: str):
    with _DB_LOCK:
        db.execute("UPDATE rooms SET name = ? WHERE id = ?", (new_name, room_id))
        db.commit()


def delete_room(room_id: int):
    with _DB_LOCK:
        lists = db.execute(
            "SELECT id FROM lists WHERE room_id = ?", (room_id,)
        ).fetchall()
        for list_row in lists:
            list_id = list_row[0]
            db.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
            db.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        db.commit()
