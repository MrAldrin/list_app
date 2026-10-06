"""Creation invitations: admins issue and revoke them; anyone with a link can
create a new room.

The rules live in `src/room_invitations.py` (docs/room-invitations.md). An
invitation never gives access to any room, also not to the room it creates:
the creator signs in with the new password.

- Admin: `/api/v1/admin/invitations` (needs admin sign-in, like `api.admin`).
- Public: `/api/v1/invitations/{token}`, the token in the path like the
  page URL `/create-room/{token}`. Only its sha256 is stored.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from starlette.concurrency import run_in_threadpool

from api.admin import require_admin
from api.errors import ApiError
from api.requests import json_object, parse_body
from api.session import MAX_PASSWORD_LENGTH
from database_crud import normalize_display_name
from room_invitations import (
    InvitationUnavailable,
    create_invitation,
    create_room_from_invitation,
    get_invitations,
    invitation_is_active,
    invitation_status,
    revoke_invitation,
)

# SQLite integers are 64-bit; a larger id could never match a row.
MAX_INVITATION_ID = 2**63 - 1

admin_router = APIRouter(
    prefix="/admin/invitations", dependencies=[Depends(require_admin)]
)
router = APIRouter(prefix="/invitations")


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateRoomBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    password: StrictStr = Field(max_length=MAX_PASSWORD_LENGTH)


def _utc(timestamp: int | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _invitation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "status": invitation_status(row),
        "created_at": _utc(row["created_at"]),
        "expires_at": _utc(row["expires_at"]),
        "revoked_at": _utc(row["revoked_at"]),
    }


# Admin


@admin_router.get("")
async def invitations() -> dict[str, Any]:
    """Every kept invitation, newest first. Reading
    the list deletes records that are inactive for seven days."""
    rows = await run_in_threadpool(get_invitations)
    return {"invitations": [_invitation(row) for row in rows]}


@admin_router.post("")
async def issue(body: dict[str, Any] = Depends(json_object)) -> dict[str, Any]:
    """A new 7-day invitation. The token is in this answer only."""
    parse_body(EmptyBody, body)

    def create() -> tuple[str, dict[str, Any] | None]:
        invitation_id, token = create_invitation()
        row = next(
            (row for row in get_invitations() if row["id"] == invitation_id), None
        )
        return token, row

    token, row = await run_in_threadpool(create)
    if row is None:  # Cannot happen: a new invitation is never pruned.
        raise ApiError(500, "internal_error")
    return {"invitation": _invitation(row), "token": token}


@admin_router.post("/{invitation_id}/revoke")
async def revoke(
    invitation_id: int = Path(ge=1, le=MAX_INVITATION_ID),
    body: dict[str, Any] = Depends(json_object),
) -> dict[str, Any]:
    """Stops further room creation with this invitation. Rooms made with it
    stay. An unknown or already revoked invitation changes nothing."""
    parse_body(EmptyBody, body)
    await run_in_threadpool(revoke_invitation, invitation_id)
    return {}


# Public: anyone with the link


@router.get("/{token}")
def check(token: str) -> dict[str, Any]:
    """200 when the invitation can still create a room. Never says why not."""
    if not invitation_is_active(token):
        raise ApiError(404, "invitation_unavailable")
    return {}


@router.post("/{token}/rooms")
def create_room(token: str, body: dict[str, Any] = Depends(json_object)) -> dict:
    """Creates a room. The invitation is checked again inside the write
    transaction. The creator is not signed in: no cookie is set."""
    data = parse_body(CreateRoomBody, body)
    try:
        slug = create_room_from_invitation(token, data.name, data.password)
    except InvitationUnavailable:
        raise ApiError(404, "invitation_unavailable") from None
    except ValueError as error:
        raise ApiError(422, "invalid_request", str(error)) from None
    return {"room": {"slug": slug, "name": normalize_display_name(data.name)}}
