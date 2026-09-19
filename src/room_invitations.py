"""Creation invitations are separate from ongoing room authorization.

Admin authentication is enforced by UI callers of management functions. The
public creation function always checks the invitation itself, transactionally.
"""

import hashlib
import secrets
import time

import bcrypt

from database_crud import _DB_LOCK, normalize_item_name
from database_setup import db

INVITATION_LIFETIME = 7 * 24 * 60 * 60


class InvitationUnavailable(ValueError):
    """The invitation is unknown, expired, or revoked."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_invitation() -> tuple[int, str]:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with _DB_LOCK, db:
        result = db.execute(
            "INSERT INTO room_invitations (token_hash, created_at, expires_at) "
            "VALUES (?, ?, ?)",
            (_hash(token), now, now + INVITATION_LIFETIME),
        )
        return result.lastrowid, token


def get_invitations() -> list[dict]:
    with _DB_LOCK:
        rows = db.execute(
            "SELECT id, created_at, expires_at, revoked_at "
            "FROM room_invitations ORDER BY id DESC"
        ).fetchall()
    return [
        dict(zip(("id", "created_at", "expires_at", "revoked_at"), row, strict=True))
        for row in rows
    ]


def revoke_invitation(invitation_id: int) -> None:
    with _DB_LOCK, db:
        db.execute(
            "UPDATE room_invitations SET revoked_at = ? "
            "WHERE id = ? AND revoked_at IS NULL",
            (int(time.time()), invitation_id),
        )


def _is_active_locked(token: str) -> bool:
    return bool(
        token
        and db.execute(
            "SELECT 1 FROM room_invitations "
            "WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?",
            (_hash(token), int(time.time())),
        ).fetchone()
    )


def invitation_is_active(token: str) -> bool:
    with _DB_LOCK:
        return _is_active_locked(token)


def create_room_from_invitation(token: str, name: str, password: str) -> str:
    # Reject invalid links before spending CPU on bcrypt, then recheck at write time.
    if not invitation_is_active(token):
        raise InvitationUnavailable("This invitation is invalid or no longer active.")
    name = normalize_item_name(name)
    if not name or len(name) > 100:
        raise ValueError("Room name must contain 1-100 characters.")
    if not password.strip() or len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be nonblank and at most 72 UTF-8 bytes.")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    slug = secrets.token_urlsafe(18)
    with _DB_LOCK:
        try:
            db.execute("BEGIN IMMEDIATE")
            if not _is_active_locked(token):
                raise InvitationUnavailable(
                    "This invitation is invalid or no longer active."
                )
            db.execute(
                "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
                (name, slug, password_hash),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    return slug
