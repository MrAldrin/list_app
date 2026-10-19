"""Creation invitations are separate from ongoing room authorization.

Admin authentication is enforced by UI callers of management functions. The
public creation function always checks the invitation itself, transactionally.
"""

import secrets
import time

from database_crud import (
    _DB_LOCK,
    check_new_room_password,
    normalize_display_name,
    transaction,
)
from database_setup import db, inserted_row_id
from field_limits import MAX_NAME_LENGTH, MAX_ROOMS_PER_INVITATION
from identifiers import token_hash
from password_hashing import hash_password

INVITATION_LIFETIME = 7 * 24 * 60 * 60
INVITATION_RETENTION = 7 * 24 * 60 * 60
UNAVAILABLE_MESSAGE = "This invitation is invalid or no longer active."


class InvitationUnavailable(ValueError):
    """The invitation is unknown, expired, or revoked."""


def create_invitation() -> tuple[int, str]:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with transaction(write=True):
        result = db.execute(
            "INSERT INTO room_invitations (token_hash, created_at, expires_at) "
            "VALUES (?, ?, ?)",
            (token_hash(token), now, now + INVITATION_LIFETIME),
        )
        return inserted_row_id(result), token


def get_invitations() -> list[dict]:
    """Prune records inactive for seven days when the admin list is loaded.

    Use the earlier of expiry and revocation: revoking an already expired
    invitation must not extend its retention period. Room data is independent.
    """
    cutoff = int(time.time()) - INVITATION_RETENTION
    with transaction(write=True):
        db.execute(
            "DELETE FROM room_invitations WHERE expires_at <= ? OR revoked_at <= ?",
            (cutoff, cutoff),
        )
        rows = db.execute(
            "SELECT id, created_at, expires_at, revoked_at "
            "FROM room_invitations ORDER BY id DESC"
        ).fetchall()
    return [
        dict(zip(("id", "created_at", "expires_at", "revoked_at"), row, strict=True))
        for row in rows
    ]


def invitation_status(invitation: dict) -> str:
    """`revoked`, `active` or `expired`, for an admin listing row.

    Revocation wins over expiry.
    """
    if invitation["revoked_at"] is not None:
        return "revoked"
    if invitation["expires_at"] > time.time():
        return "active"
    return "expired"


def revoke_invitation(invitation_id: int) -> None:
    with transaction(write=True):
        db.execute(
            "UPDATE room_invitations SET revoked_at = ? "
            "WHERE id = ? AND revoked_at IS NULL",
            (int(time.time()), invitation_id),
        )


def _is_active_locked(token: str) -> bool:
    """True when the invitation can create a room now: not revoked, not expired,
    and under its room limit. An invitation at its limit counts as unavailable."""
    return bool(
        token
        and db.execute(
            "SELECT 1 FROM room_invitations "
            "WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ? "
            "AND rooms_created < ?",
            (token_hash(token), int(time.time()), MAX_ROOMS_PER_INVITATION),
        ).fetchone()
    )


def invitation_is_active(token: str) -> bool:
    with _DB_LOCK:
        return _is_active_locked(token)


def create_room_from_invitation(token: str, name: str, password: str) -> str:
    # Reject invalid or used-up links before spending CPU on bcrypt, then recheck
    # and count the room in the same write transaction (BEGIN IMMEDIATE).
    if not invitation_is_active(token):
        raise InvitationUnavailable(UNAVAILABLE_MESSAGE)
    name = normalize_display_name(name)
    if not name or len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Room name must contain 1-{MAX_NAME_LENGTH} characters.")
    check_new_room_password(password)
    password_hash = hash_password(password)
    slug = secrets.token_urlsafe(18)
    with transaction(write=True):
        if not _is_active_locked(token):
            raise InvitationUnavailable(UNAVAILABLE_MESSAGE)
        db.execute(
            "UPDATE room_invitations SET rooms_created = rooms_created + 1 "
            "WHERE token_hash = ?",
            (token_hash(token),),
        )
        db.execute(
            "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
            (name, slug, password_hash),
        )
    return slug
