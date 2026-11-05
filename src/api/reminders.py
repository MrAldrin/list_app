"""Personal reminder settings for this device, under /api/v1/rooms/{slug}/reminders.

- `POST enrollment`: create or resume this device's enrollment in the room. The
  only route that creates an installation, sets the device cookie or activates
  a saved grant.
- `GET/PATCH preferences`: this device's enrollment in the room (mode, summary
  time, opt-out). Needs the room cookie and the device cookie.
- `GET/PATCH preferences/device`: device-wide settings that apply to every room
  this device is enrolled in. Needs the room cookie and the device cookie.

Every route checks room access first, then the device cookie. Personal writes
use their own op namespace (`reminder_processed_ops`), never `processed_ops`.
Nothing here changes a room's change sequence or its live stream.
"""

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, StrictBool, StrictInt, StrictStr

from api.access import is_https, room_access, room_token
from api.cookies import set_cookie
from api.errors import ApiError
from api.ops import Uuid
from api.requests import JsonBody, StrictBody, parse_body
from identifiers import token_hash
from reminders import identity
from reminders.due_schedule import CLOCK_TIME
from reminders.identity import (
    ENROLLMENT_SCOPE,
    INSTALLATION_SCOPE,
    MAX_ENROLLMENTS_PER_ROOM,
    MAX_ROOMS_PER_DEVICE,
    STATUS_OPTED_OUT,
)
from reminders.zoned_time import TimeZoneUnavailable, load_zone
from room_cookies import HOST_PREFIX, MAX_AGE

router = APIRouter()

# The device cookie: a random installation secret, HttpOnly, one year.
PLAIN_DEVICE_COOKIE = "listapp-device"

# Longest device secret accepted from a cookie; issued secrets are 43 characters.
MAX_SECRET_LENGTH = 256

Revision = Annotated[StrictInt, Field(ge=1)]
Timezone = Annotated[StrictStr, Field(min_length=1, max_length=64)]
ClockTime = Annotated[StrictStr, Field(min_length=5, max_length=5)]
DailyCap = Annotated[StrictInt, Field(ge=1, le=50)]
SpacingMinutes = Annotated[StrictInt, Field(ge=1, le=60)]
OverdueRepeatDays = Annotated[StrictInt, Field(ge=1, le=30)]
Mode = Literal["quiet", "daily_summary", "scheduled", "custom"]
ContentPrivacy = Literal["generic", "counts", "names"]


class QuietHours(StrictBody):
    start: ClockTime
    end: ClockTime


class EnrollmentBody(StrictBody):
    op_id: Uuid
    # None for a new enrollment; otherwise the enrollment's current revision.
    base_revision: Revision | None = None
    # Required only when this device has no installation yet.
    timezone: Timezone | None = None
    mode: Mode | None = None
    summary_time: ClockTime | None = None

    # Absent and null hash alike only for fields that are always sent; an
    # optional field left out of the request is not hashed at all.
    hash_omit_if_unsent: ClassVar[frozenset[str]] = frozenset(
        {"base_revision", "timezone", "mode", "summary_time"}
    )
    # Hashed with the body, never sent: the same op_id used for another action
    # (PATCH preferences) is a different request, so it gets 409 op_id_reused.
    action: ClassVar[str] = "enroll"


class EnrollmentPatchBody(StrictBody):
    op_id: Uuid
    base_revision: Revision
    mode: Mode | None = None
    summary_time: ClockTime | None = None
    # Only opting out: opting back in is an explicit enrollment (POST enrollment).
    opted_out: Literal[True] | None = None

    hash_omit_if_unsent: ClassVar[frozenset[str]] = frozenset(
        {"mode", "summary_time", "opted_out"}
    )
    action: ClassVar[str] = "patch_preferences"


class DevicePatchBody(StrictBody):
    op_id: Uuid
    base_revision: Revision
    timezone: Timezone | None = None
    all_day_time: ClockTime | None = None
    # null turns quiet hours off; absent keeps the stored hours.
    quiet_hours: QuietHours | None = None
    daily_cap: DailyCap | None = None
    spacing_minutes: SpacingMinutes | None = None
    paused: StrictBool | None = None
    content_privacy: ContentPrivacy | None = None
    # null turns the overdue repeat off; absent keeps the stored value.
    overdue_repeat_days: OverdueRepeatDays | None = None

    hash_omit_if_unsent: ClassVar[frozenset[str]] = frozenset(
        {
            "timezone",
            "all_day_time",
            "quiet_hours",
            "daily_cap",
            "spacing_minutes",
            "paused",
            "content_privacy",
            "overdue_repeat_days",
        }
    )


# Settings that may be sent as null (off). Every other setting must be a value.
_NULLABLE_DEVICE_FIELDS = frozenset({"quiet_hours", "overdue_repeat_days"})
_CONTROL_FIELDS = frozenset({"op_id", "base_revision"})


def device_cookie_name(request: Request) -> str:
    """`__Host-` on HTTPS, the plain name over plain HTTP (see api/access.py)."""
    if is_https(request):
        return HOST_PREFIX + PLAIN_DEVICE_COOKIE
    return PLAIN_DEVICE_COOKIE


def device_secret(request: Request) -> str | None:
    secret = request.cookies.get(device_cookie_name(request))
    if not secret or len(secret) > MAX_SECRET_LENGTH:
        return None
    return secret


def installation_for_request(request: Request) -> int | None:
    """The device this request's cookie names, or None. Read only."""
    return identity.installation_id_for_secret_locked(device_secret(request))


def _require_device(request: Request) -> int:
    installation_id = installation_for_request(request)
    if installation_id is None:
        raise ApiError(403, "not_enrolled")
    return installation_id


def _enrollment_view(installation_id: int, room_id: int) -> dict[str, Any]:
    row = identity.enrollment_row_locked(installation_id, room_id)
    if row is None:
        return {"state": identity.STATE_NOT_ENROLLED, "revision": None}
    return {
        "state": identity.saved_grant_state_locked(installation_id, room_id),
        "mode": row["mode"],
        "summary_time": row["summary_time"],
        "revision": row["revision"],
        "activated_at": row["activated_at"],
    }


def _device_view(installation_id: int) -> dict[str, Any]:
    settings = identity.installation_settings_locked(installation_id)
    quiet = None
    if settings["quiet_start"] is not None:
        quiet = {"start": settings["quiet_start"], "end": settings["quiet_end"]}
    return {
        "revision": settings["revision"],
        "timezone": settings["timezone"],
        "all_day_time": settings["all_day_time"],
        "quiet_hours": quiet,
        "daily_cap": settings["daily_cap"],
        "spacing_minutes": settings["spacing_minutes"],
        "paused": bool(settings["paused"]),
        "content_privacy": settings["content_privacy"],
        "overdue_repeat_days": settings["overdue_repeat_days"],
    }


def _check_zone(name: str) -> None:
    try:
        load_zone(name)
    except TimeZoneUnavailable:
        raise ApiError(422, "invalid_request", "Unknown time zone.") from None


def _check_clock(value: str) -> None:
    if not CLOCK_TIME.fullmatch(value):
        raise ApiError(422, "invalid_request", "Times are HH:MM.")


def _check_revision(current: int | None, base: int | None) -> None:
    if current != base:
        raise ApiError(409, "revision_conflict")


def personal_request_hash(body: BaseModel) -> str:
    """The hash of a personal op: its action name and body, in canonical JSON.

    The action is part of the hash, so one op_id used for two actions (for
    example POST enrollment and PATCH preferences) is 409 `op_id_reused`, not a
    replay of the other action. A body's own hash rules are kept.
    """
    action = getattr(body, "action", "")
    data = body.model_dump(mode="json")
    for name in getattr(body, "hash_omit_if_null", frozenset()):
        if data.get(name) is None:
            data.pop(name, None)
    for name in getattr(body, "hash_omit_if_unsent", frozenset()):
        if name not in body.model_fields_set:
            data.pop(name, None)
    canonical = json.dumps(
        {"action": action, **data}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_personal_once_locked(
    scope: str,
    installation_id: int,
    room_id: int | None,
    op_id: str,
    body_hash: str,
    run: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Replay the stored result for this personal op, or run it and store it.

    Call inside room_access(write=True), after the room and device checks, and
    before any revision check: a replay returns the first result unchanged.
    Returns (response, replayed). The same op_id with another body is 409
    `op_id_reused`.
    """
    stored = identity.find_personal_op_locked(scope, installation_id, room_id, op_id)
    if stored is not None:
        stored_hash, response_json = stored
        if stored_hash != body_hash:
            raise ApiError(409, "op_id_reused")
        return json.loads(response_json), True
    response = run()
    identity.store_personal_op_locked(
        scope, installation_id, room_id, op_id, body_hash, json.dumps(response)
    )
    return response, False


@router.post("/rooms/{slug}/reminders/enrollment")
def enroll(slug: str, request: Request, body: JsonBody) -> Response:
    """Create or resume this device's enrollment in the room: the explicit action.

    Sets the device cookie (renewing its one-year lifetime). The only route that
    activates a saved grant. A replay returns the stored result with the grant's
    current state, so it never reactivates a grant that was cut since.
    """
    data = parse_body(EnrollmentBody, body)
    body_hash = personal_request_hash(data)
    token_digest = token_hash(room_token(request, slug) or "")
    with room_access(request, slug, write=True) as room:
        moment = identity.current_time()
        installation_id = installation_for_request(request)
        secret = device_secret(request)
        if installation_id is None:
            # A new device. A lost response leaves no cookie to replay with, so
            # a retry makes another installation (see docs/api-reminders.md).
            if data.timezone is None:
                raise ApiError(422, "invalid_request", "A time zone is required.")
            _check_zone(data.timezone)
            secret = identity.new_installation_secret()
            installation_id = identity.create_installation_locked(
                secret, data.timezone, now=moment
            )
        elif data.timezone is not None:
            stored_zone = identity.installation_settings_locked(installation_id)[
                "timezone"
            ]
            if data.timezone != stored_zone:
                raise ApiError(
                    422,
                    "invalid_request",
                    "Change the device time zone in the device settings.",
                )
        result, replayed = _enroll_once(
            installation_id, room.room_id, token_digest, data, body_hash, moment
        )
        if replayed:
            # Refresh the dynamic grant state inside the same lock. The stored
            # result is otherwise unchanged, and no cookie is reset.
            result["enrollment"]["state"] = identity.saved_grant_state_locked(
                installation_id, room.room_id
            )
            return JSONResponse(result)
    response = JSONResponse(result)
    assert secret is not None  # Set on create, or read from the valid cookie.
    set_cookie(response, request, device_cookie_name(request), secret, MAX_AGE)
    return response


def _enroll_once(
    installation_id: int,
    room_id: int,
    token_digest: str,
    data: EnrollmentBody,
    body_hash: str,
    moment: datetime,
) -> tuple[dict[str, Any], bool]:
    """Run the enrollment once per op, or replay it. Call inside a write block."""

    def run() -> dict[str, Any]:
        row = identity.enrollment_row_locked(installation_id, room_id)
        _check_revision(row["revision"] if row else None, data.base_revision)
        if row is None:
            if identity.installation_enrollment_count_locked(installation_id) >= (
                MAX_ROOMS_PER_DEVICE
            ):
                raise ApiError(
                    422,
                    "invalid_request",
                    "This device has enrolled in too many rooms.",
                )
            if identity.room_enrollment_count_locked(room_id) >= (
                MAX_ENROLLMENTS_PER_ROOM
            ):
                raise ApiError(
                    422, "invalid_request", "This room has too many reminder devices."
                )
        if data.summary_time is not None:
            _check_clock(data.summary_time)
        # Only a real enrollment starts a new device and grant lifetime; a replay
        # returns the stored result and extends nothing.
        identity.renew_installation_locked(installation_id, now=moment)
        identity.enroll_room_locked(
            installation_id,
            room_id,
            token_digest,
            data.mode,
            data.summary_time,
            now=moment,
        )
        return {"enrollment": _enrollment_view(installation_id, room_id)}

    return run_personal_once_locked(
        ENROLLMENT_SCOPE, installation_id, room_id, data.op_id, body_hash, run
    )


@router.get("/rooms/{slug}/reminders/preferences")
def get_preferences(slug: str, request: Request) -> dict[str, Any]:
    """This device's enrollment in the room. Read only: never enrolls or renews."""
    with room_access(request, slug) as room:
        installation_id = installation_for_request(request)
        if installation_id is None:
            return {
                "enrollment": {"state": identity.STATE_NOT_ENROLLED, "revision": None}
            }
        return {"enrollment": _enrollment_view(installation_id, room.room_id)}


@router.patch("/rooms/{slug}/reminders/preferences")
def patch_preferences(slug: str, request: Request, body: JsonBody) -> dict[str, Any]:
    """Change this device's enrollment settings in the room. Never activates a grant."""
    data = parse_body(EnrollmentPatchBody, body)
    body_hash = personal_request_hash(data)
    with room_access(request, slug, write=True) as room:
        installation_id = _require_device(request)
        if identity.enrollment_row_locked(installation_id, room.room_id) is None:
            raise ApiError(403, "not_enrolled")

        def run() -> dict[str, Any]:
            current = identity.enrollment_row_locked(installation_id, room.room_id)
            if current is None:
                raise ApiError(403, "not_enrolled")
            _check_revision(current["revision"], data.base_revision)
            changes: dict[str, Any] = {}
            if data.mode is not None:
                changes["mode"] = data.mode
            if data.summary_time is not None:
                _check_clock(data.summary_time)
                changes["summary_time"] = data.summary_time
            if data.opted_out:
                changes["status"] = STATUS_OPTED_OUT
            if changes:
                identity.update_enrollment_locked(
                    installation_id, room.room_id, changes
                )
            return {"enrollment": _enrollment_view(installation_id, room.room_id)}

        response, replayed = run_personal_once_locked(
            ENROLLMENT_SCOPE, installation_id, room.room_id, data.op_id, body_hash, run
        )
        if replayed:
            # A stored PATCH result may predate a sign-out or password change. The
            # dynamic grant state is refreshed inside the lock; nothing is reapplied.
            response["enrollment"]["state"] = identity.saved_grant_state_locked(
                installation_id, room.room_id
            )
    return response


@router.get("/rooms/{slug}/reminders/preferences/device")
def get_device(slug: str, request: Request) -> dict[str, Any]:
    """Device-wide settings. Read only: never creates the device."""
    with room_access(request, slug):
        installation_id = installation_for_request(request)
        if installation_id is None:
            return {"device": None}
        return {"device": _device_view(installation_id)}


@router.patch("/rooms/{slug}/reminders/preferences/device")
def patch_device(slug: str, request: Request, body: JsonBody) -> dict[str, Any]:
    """Change this device's settings. They apply to every room it is enrolled in."""
    data = parse_body(DevicePatchBody, body)
    body_hash = personal_request_hash(data)
    with room_access(request, slug, write=True):
        installation_id = _require_device(request)

        def run() -> dict[str, Any]:
            current = identity.installation_revision_locked(installation_id)
            _check_revision(current, data.base_revision)
            changes = _device_changes(data)
            if changes:
                identity.update_installation_settings_locked(installation_id, changes)
            return {"device": _device_view(installation_id)}

        response, _replayed = run_personal_once_locked(
            INSTALLATION_SCOPE, installation_id, None, data.op_id, body_hash, run
        )
    return response


def _device_changes(data: DevicePatchBody) -> dict[str, Any]:
    """The device columns a PATCH sets. Absent settings are left alone."""
    changes: dict[str, Any] = {}
    for name in data.model_fields_set - _CONTROL_FIELDS:
        value = getattr(data, name)
        if value is None and name not in _NULLABLE_DEVICE_FIELDS:
            raise ApiError(422, "invalid_request", f"{name} cannot be null.")
        if name == "timezone":
            _check_zone(value)
            changes["timezone"] = value
        elif name == "all_day_time":
            _check_clock(value)
            changes["all_day_time"] = value
        elif name == "quiet_hours":
            if value is None:
                changes["quiet_start"] = None
                changes["quiet_end"] = None
            else:
                _check_clock(value.start)
                _check_clock(value.end)
                if value.start == value.end:
                    raise ApiError(
                        422, "invalid_request", "Quiet hours need two times."
                    )
                changes["quiet_start"] = value.start
                changes["quiet_end"] = value.end
        else:
            changes[name] = value
    return changes
