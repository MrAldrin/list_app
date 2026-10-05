"""Admin endpoints: sign in with APP_PASSWORD, the room overview, creating a
room and resetting a room password. Ported from NiceGUI's /admin.

Admin sign-in is NiceGUI's own flag in `app.storage.user` (see
`src/admin_access.py`), so it is shared with NiceGUI's /admin in the same
browser. Admin never grants room access: these endpoints send only room names
and slugs, and never set a room cookie. Room endpoints ignore admin sign-in.

The endpoints are `async`: NiceGUI's user storage must be changed on its
event loop. Database work (bcrypt) runs in a worker thread.
"""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import Response
from nicegui import app
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from starlette.concurrency import run_in_threadpool

from admin_access import ADMIN_STORAGE_KEY, admin_password_matches
from api.errors import ApiError
from api.requests import json_object, parse_body
from api.session import MAX_PASSWORD_LENGTH
from database_crud import (
    check_new_room_password,
    check_password_length,
    create_room,
    get_room_details_by_slug,
    get_rooms,
    reset_room_password_by_slug,
)
from live_updates import wake_streams

# Message as NiceGUI's admin login shows it.
WRONG_ADMIN_PASSWORD = "Wrong password"


def admin_signed_in() -> bool:
    return bool(app.storage.user.get(ADMIN_STORAGE_KEY, False))


async def require_admin() -> None:
    """Dependency: 401 `admin_required` unless this browser is signed in as admin."""
    if not admin_signed_in():
        raise ApiError(401, "admin_required")


# Sign-in needs no admin; everything in `admin_only` does. The admin check runs
# after the router-wide same-origin check and before the body is read.
router = APIRouter(prefix="/admin")
admin_only = APIRouter(dependencies=[Depends(require_admin)])


class AdminSignInBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: StrictStr = Field(max_length=MAX_PASSWORD_LENGTH)


class CreateRoomBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    password: StrictStr = Field(max_length=MAX_PASSWORD_LENGTH)


class ResetPasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: StrictStr = Field(max_length=MAX_PASSWORD_LENGTH)


@router.post("/session")
async def sign_in(body: dict[str, Any] = Depends(json_object)) -> dict[str, Any]:
    password = parse_body(AdminSignInBody, body).password
    if not admin_password_matches(password):
        # As NiceGUI: a wrong password does not sign out an admin session.
        raise ApiError(401, "invalid_password", WRONG_ADMIN_PASSWORD)
    app.storage.user[ADMIN_STORAGE_KEY] = True
    return {}


@router.get("/session")
async def who_am_i() -> dict[str, Any]:
    await require_admin()
    return {}


@router.delete("/session")
async def sign_out() -> Response:
    app.storage.user[ADMIN_STORAGE_KEY] = False
    return Response(status_code=204)


def _room(details: dict[str, Any]) -> dict[str, str]:
    return {"slug": details["slug"], "name": details["name"]}


@admin_only.get("/rooms")
async def rooms() -> dict[str, Any]:
    """Every room, by name ignoring case (NiceGUI's overview order)."""
    found = await run_in_threadpool(get_rooms)
    return {"rooms": [_room(room) for room in found]}


@admin_only.post("/rooms")
async def new_room(body: dict[str, Any] = Depends(json_object)) -> dict[str, Any]:
    data = parse_body(CreateRoomBody, body)

    def create() -> dict[str, Any] | None:
        check_password_length(data.password)
        _room_id, slug = create_room(data.name, data.password)
        return get_room_details_by_slug(slug)

    try:
        details = await run_in_threadpool(create)
    except ValueError as error:
        # NiceGUI's texts: "Room name cannot be empty", "Password cannot be empty".
        raise ApiError(422, "invalid_request", str(error)) from None
    if details is None:  # Deleted again before we read it back.
        raise ApiError(404, "room_unavailable")
    return {"room": _room(details)}


@admin_only.post("/rooms/{slug}/password")
async def reset_password(
    slug: str,
    background: BackgroundTasks,
    body: dict[str, Any] = Depends(json_object),
) -> dict[str, Any]:
    new_password = parse_body(ResetPasswordBody, body).new_password
    try:
        check_new_room_password(new_password)
    except ValueError as error:
        raise ApiError(422, "invalid_request", str(error)) from None
    room_id = await run_in_threadpool(reset_room_password_by_slug, slug, new_password)
    if room_id is None:
        raise ApiError(404, "room_unavailable")
    # Every token of the room is revoked: its streams send `revoked`.
    background.add_task(wake_streams, room_id)
    return {}


router.include_router(admin_only)
