"""This device (installation) and its room enrollments: storage and grant state.

An installation is one browser or app install. Its secret is random, issued by
the server, and stored only as a sha256 hash. An enrollment joins one
installation to one room. It saves the hash of the room token that authorized
it and the room's authorization version at that time. A saved grant is valid
only while that token is live, the room version has not changed, and both the
installation and the grant have not expired.

Expiry (UTC, `YYYY-MM-DDTHH:MM:SSZ` text, compared as text):

- `reminder_installations.expires_at`: one device lifetime after creation or
  the last explicit enrollment (the device cookie has the same lifetime).
- `reminder_enrollments.expires_at`: the earlier of one device lifetime after
  the last explicit enrollment and the authorizing room token's creation time
  plus one room lifetime. Room tokens have no stored expiry, so this bound uses
  the room cookie's one-year lifetime. A saved grant never outlives it.

Time comes from `current_time()`; tests replace it to use a fake clock.

Every function that writes runs inside a write transaction the caller holds
(`room_access(..., write=True)` or `transaction(write=True)`). The grant check
(`saved_grant_state_locked`) only reads.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from database_setup import db
from identifiers import token_hash

# Most rooms one installation can enroll in, and most installations one room can have.
MAX_ROOMS_PER_DEVICE = 20
MAX_ENROLLMENTS_PER_ROOM = 50

# Lifetimes. The device cookie and the room cookie both last one year.
DEVICE_LIFETIME = timedelta(days=365)
ROOM_TOKEN_LIFETIME = timedelta(days=365)

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
# SQLite's CURRENT_TIMESTAMP, which stores room_access_tokens.created_at.
SQLITE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Stored enrollment status. `revoked`: sign-out or a password change cut the
# saved grant, so only an explicit resume brings it back.
STATUS_ACTIVE = "active"
STATUS_OPTED_OUT = "opted_out"
STATUS_REVOKED = "revoked"

# Reported states that differ from the stored status (see saved_grant_state_locked).
STATE_NOT_ENROLLED = "not_enrolled"
STATE_NEEDS_RESUME = "needs_resume"

# Idempotency namespaces for personal writes; never the shared processed_ops.
INSTALLATION_SCOPE = "installation"
ENROLLMENT_SCOPE = "enrollment"

MODES = ("quiet", "daily_summary", "scheduled", "custom")
DEFAULT_MODE = "daily_summary"
DEFAULT_SUMMARY_TIME = "09:00"
CONTENT_PRIVACY = ("generic", "counts", "names")

# Device setting columns, as the API names them (quiet hours are two columns).
DEVICE_COLUMNS = (
    "revision",
    "timezone",
    "all_day_time",
    "quiet_start",
    "quiet_end",
    "daily_cap",
    "spacing_minutes",
    "paused",
    "content_privacy",
    "overdue_repeat_days",
)


def current_time() -> datetime:
    """The current UTC time. Tests replace this with a fake clock."""
    return datetime.now(UTC)


def stamp(moment: datetime) -> str:
    """A UTC moment in the stored text format."""
    return moment.astimezone(UTC).strftime(TIME_FORMAT)


def new_installation_secret() -> str:
    return secrets.token_urlsafe(32)


def installation_id_for_secret_locked(secret: str | None) -> int | None:
    """The live installation whose secret this is, or None.

    None for an absent, forged, too long or expired secret. Read only.
    """
    if not secret or len(secret) > 256:
        return None
    row = db.execute(
        "SELECT id FROM reminder_installations "
        "WHERE secret_hash = ? AND expires_at > ?",
        (token_hash(secret), stamp(current_time())),
    ).fetchone()
    return row[0] if row else None


def create_installation_locked(secret: str, timezone: str) -> int:
    """Store a new installation with default device settings. Returns its ID."""
    now = current_time()
    cursor = db.execute(
        "INSERT INTO reminder_installations "
        "(secret_hash, timezone, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (
            token_hash(secret),
            timezone,
            stamp(now),
            stamp(now + DEVICE_LIFETIME),
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("The installation insert did not return an ID")
    return cursor.lastrowid


def renew_installation_locked(installation_id: int) -> None:
    """Start a new device lifetime. Only explicit enrollment calls this."""
    db.execute(
        "UPDATE reminder_installations SET expires_at = ? WHERE id = ?",
        (stamp(current_time() + DEVICE_LIFETIME), installation_id),
    )


def installation_settings_locked(installation_id: int) -> dict[str, Any]:
    """The device settings of one installation, keyed by DEVICE_COLUMNS."""
    row = db.execute(
        f"SELECT {', '.join(DEVICE_COLUMNS)} FROM reminder_installations WHERE id = ?",
        (installation_id,),
    ).fetchone()
    return dict(zip(DEVICE_COLUMNS, row, strict=True))


def update_installation_settings_locked(
    installation_id: int, changes: dict[str, Any]
) -> None:
    """Set some device settings and bump the installation revision.

    Keys must be names from DEVICE_COLUMNS (fixed names, never user text).
    """
    unknown = set(changes) - set(DEVICE_COLUMNS) - {"revision"}
    if unknown:
        raise ValueError(f"Not a device setting: {sorted(unknown)}")
    assignments = ", ".join(f"{column} = ?" for column in changes)
    db.execute(
        f"UPDATE reminder_installations SET {assignments}, revision = revision + 1 "
        "WHERE id = ?",
        (*changes.values(), installation_id),
    )


def installation_revision_locked(installation_id: int) -> int:
    row = db.execute(
        "SELECT revision FROM reminder_installations WHERE id = ?", (installation_id,)
    ).fetchone()
    return row[0]


def enrollment_row_locked(installation_id: int, room_id: int) -> dict[str, Any] | None:
    """This device's enrollment in one room as a dict, or None. Read only."""
    row = db.execute(
        "SELECT status, token_hash, authorization_version, mode, summary_time, "
        "revision, activated_at, expires_at FROM reminder_enrollments "
        "WHERE installation_id = ? AND room_id = ?",
        (installation_id, room_id),
    ).fetchone()
    if row is None:
        return None
    keys = (
        "status",
        "token_hash",
        "authorization_version",
        "mode",
        "summary_time",
        "revision",
        "activated_at",
        "expires_at",
    )
    return dict(zip(keys, row, strict=True))


def installation_enrollment_count_locked(installation_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM reminder_enrollments WHERE installation_id = ?",
        (installation_id,),
    ).fetchone()[0]


def room_enrollment_count_locked(room_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM reminder_enrollments WHERE room_id = ?", (room_id,)
    ).fetchone()[0]


def _token_is_live_locked(room_id: int, saved_hash: str, saved_version: int) -> bool:
    """True if this token still authorizes the room at the saved version."""
    row = db.execute(
        """
        SELECT 1
        FROM rooms AS r
        JOIN room_access_tokens AS t ON t.room_id = r.id
        WHERE r.id = ?
          AND t.token_hash = ?
          AND t.revoked_at IS NULL
          AND t.authorization_version = r.authorization_version
          AND r.authorization_version = ?
        """,
        (room_id, saved_hash, saved_version),
    ).fetchone()
    return row is not None


def saved_grant_state_locked(installation_id: int, room_id: int) -> str:
    """The grant state of this device in this room. Pure validation: never writes.

    Returns `not_enrolled` (no row), `opted_out`, `active` (the installation and
    the saved grant have not expired, and the saved token is still live at the
    saved room version) or `needs_resume` (revoked, expired, or no longer
    matching the room). The installation's own expiry is checked here as well,
    so a grant cannot read as active after its device has expired. Only an
    explicit enrollment restores a grant.
    """
    row = enrollment_row_locked(installation_id, room_id)
    if row is None:
        return STATE_NOT_ENROLLED
    if row["status"] == STATUS_OPTED_OUT:
        return STATUS_OPTED_OUT
    if row["status"] == STATUS_REVOKED:
        return STATE_NEEDS_RESUME
    now = stamp(current_time())
    installation_expires_at = db.execute(
        "SELECT expires_at FROM reminder_installations WHERE id = ?",
        (installation_id,),
    ).fetchone()
    if installation_expires_at is None or installation_expires_at[0] <= now:
        return STATE_NEEDS_RESUME
    if row["expires_at"] <= now:
        return STATE_NEEDS_RESUME
    if _token_is_live_locked(room_id, row["token_hash"], row["authorization_version"]):
        return STATUS_ACTIVE
    return STATE_NEEDS_RESUME


def room_authorization_version_locked(room_id: int) -> int:
    return db.execute(
        "SELECT authorization_version FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]


def _token_created_at_locked(room_id: int, authorizing_token_hash: str) -> datetime:
    """When the authorizing room token was issued (UTC)."""
    row = db.execute(
        "SELECT created_at FROM room_access_tokens WHERE room_id = ? AND token_hash = ?",
        (room_id, authorizing_token_hash),
    ).fetchone()
    if row is None:
        raise ValueError("The authorizing room token is not stored")
    return datetime.strptime(row[0], SQLITE_TIME_FORMAT).replace(tzinfo=UTC)


def grant_expiry_locked(room_id: int, authorizing_token_hash: str) -> str:
    """The saved grant's expiry: the earlier of a device lifetime from now and
    a room lifetime from token issue."""
    now = current_time()
    room_bound = _token_created_at_locked(room_id, authorizing_token_hash)
    return stamp(min(now + DEVICE_LIFETIME, room_bound + ROOM_TOKEN_LIFETIME))


def enroll_room_locked(
    installation_id: int,
    room_id: int,
    authorizing_token_hash: str,
    mode: str | None,
    summary_time: str | None,
) -> None:
    """Create or resume this device's enrollment, bound to the authorizing token.

    `mode` and `summary_time` of None keep the stored values (defaults on
    create). The activation time moves to now unless the grant was already
    active, so a repeated resume does not move it forward. The grant expiry is
    recomputed from this explicit action. The caller has checked the enrollment
    revision and the room authorization.
    """
    now = stamp(current_time())
    version = room_authorization_version_locked(room_id)
    expires_at = grant_expiry_locked(room_id, authorizing_token_hash)
    previous = enrollment_row_locked(installation_id, room_id)
    if previous is None:
        db.execute(
            """
            INSERT INTO reminder_enrollments (
                installation_id, room_id, token_hash, authorization_version,
                status, mode, summary_time, revision, activated_at, expires_at,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                installation_id,
                room_id,
                authorizing_token_hash,
                version,
                STATUS_ACTIVE,
                mode or DEFAULT_MODE,
                summary_time or DEFAULT_SUMMARY_TIME,
                now,
                expires_at,
                now,
            ),
        )
        return
    was_active = saved_grant_state_locked(installation_id, room_id) == STATUS_ACTIVE
    db.execute(
        """
        UPDATE reminder_enrollments
        SET token_hash = ?, authorization_version = ?, status = ?,
            mode = COALESCE(?, mode), summary_time = COALESCE(?, summary_time),
            revision = revision + 1, activated_at = ?, expires_at = ?
        WHERE installation_id = ? AND room_id = ?
        """,
        (
            authorizing_token_hash,
            version,
            STATUS_ACTIVE,
            mode,
            summary_time,
            previous["activated_at"] if was_active else now,
            expires_at,
            installation_id,
            room_id,
        ),
    )


def update_enrollment_locked(
    installation_id: int, room_id: int, changes: dict[str, Any]
) -> None:
    """Set some of mode, summary_time and status, and bump the enrollment revision.

    Never activates a grant or extends its expiry: a revoked, expired or opted-out
    enrollment comes back only through enroll_room_locked.
    """
    allowed = {"mode", "summary_time", "status"}
    if set(changes) - allowed:
        raise ValueError("Not an enrollment setting")
    assignments = ", ".join(f"{column} = ?" for column in changes)
    db.execute(
        f"UPDATE reminder_enrollments SET {assignments}, revision = revision + 1 "
        "WHERE installation_id = ? AND room_id = ?",
        (*changes.values(), installation_id, room_id),
    )


def disable_enrollments_for_token_locked(
    room_id: int, authorizing_token_hash: str
) -> None:
    """A room token was signed out or revoked: its active enrollments need a resume.

    Only enrollments in `room_id` that this token authorized are cut, so a token
    revoked through another room's slug never changes this room's grants. Opted-out
    rows keep their status. Call inside a write transaction.
    """
    db.execute(
        "UPDATE reminder_enrollments "
        "SET status = ?, revision = revision + 1 "
        "WHERE room_id = ? AND token_hash = ? AND status = ?",
        (STATUS_REVOKED, room_id, authorizing_token_hash, STATUS_ACTIVE),
    )


def disable_room_enrollments_locked(room_id: int) -> None:
    """The room password was replaced: its active enrollments need a resume."""
    db.execute(
        "UPDATE reminder_enrollments "
        "SET status = ?, revision = revision + 1 "
        "WHERE room_id = ? AND status = ?",
        (STATUS_REVOKED, room_id, STATUS_ACTIVE),
    )


def find_personal_op_locked(
    scope: str, installation_id: int, room_id: int | None, op_id: str
) -> tuple[str, str] | None:
    """(request hash, stored JSON) for this personal op in its scope, or None."""
    row = db.execute(
        "SELECT request_hash, response_json FROM reminder_processed_ops "
        "WHERE scope = ? AND installation_id = ? AND room_id IS ? AND op_id = ?",
        (scope, installation_id, room_id, op_id),
    ).fetchone()
    return (row[0], row[1]) if row else None


def store_personal_op_locked(
    scope: str,
    installation_id: int,
    room_id: int | None,
    op_id: str,
    request_hash: str,
    response_json: str,
) -> None:
    db.execute(
        "INSERT INTO reminder_processed_ops "
        "(scope, installation_id, room_id, op_id, request_hash, response_json, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            scope,
            installation_id,
            room_id,
            op_id,
            request_hash,
            response_json,
            stamp(current_time()),
        ),
    )
