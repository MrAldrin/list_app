"""Admin endpoints: sign in with APP_PASSWORD, the room overview, creating a
room and resetting a room password.

Admin sign-in has its own cookie (decision 144): a signed token made with the
current `APP_PASSWORD` (see `src/admin_access.py`). Admin never grants room
access: these endpoints send only room names and slugs, and never set a room
cookie. Room endpoints ignore admin sign-in.

Database work (bcrypt) runs in a worker thread.
"""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import StrictStr
from starlette.concurrency import run_in_threadpool

from admin_access import (
    ADMIN_SESSION_SECONDS,
    admin_password_matches,
    admin_token_valid,
    issue_admin_token,
)
from api.access import is_https
from api.cookies import clear_cookie, set_cookie
from api.errors import ApiError, error_response
from api.requests import JsonBody, Password, StrictBody, parse_body
from database_crud import (
    check_new_room_password,
    create_room,
    get_room_details_by_slug,
    get_rooms,
    reset_room_password_by_slug,
)
from live_updates import wake_streams
from room_cookies import HOST_PREFIX

# Message shown at admin sign-in.
WRONG_ADMIN_PASSWORD = "Wrong password"

# As the room cookie: `__Host-` (Secure, Path=/, no Domain) on HTTPS; the plain
# name on plain HTTP, for local network testing.
PLAIN_ADMIN_COOKIE = "listapp-admin"
ADMIN_COOKIE = HOST_PREFIX + PLAIN_ADMIN_COOKIE


def admin_cookie_name(request: Request) -> str:
    return ADMIN_COOKIE if is_https(request) else PLAIN_ADMIN_COOKIE


def admin_signed_in(request: Request) -> bool:
    """True when this request carries a valid admin cookie."""
    return admin_token_valid(request.cookies.get(admin_cookie_name(request)))


async def require_admin(request: Request) -> None:
    """Dependency: 401 `admin_required` unless this browser is signed in as admin."""
    if not admin_signed_in(request):
        raise ApiError(401, "admin_required")


# Sign-in needs no admin; everything in `admin_only` does. The admin check runs
# after the router-wide same-origin check and before the body is read.
router = APIRouter(prefix="/admin")
admin_only = APIRouter(dependencies=[Depends(require_admin)])


class AdminSignInBody(StrictBody):
    password: Password


class CreateRoomBody(StrictBody):
    name: StrictStr
    password: Password


class ResetPasswordBody(StrictBody):
    new_password: Password


@router.post("/session")
async def sign_in(request: Request, body: JsonBody) -> Response:
    password = parse_body(AdminSignInBody, body).password
    if not admin_password_matches(password):
        # A wrong password does not sign out an admin session.
        raise ApiError(401, "invalid_password", WRONG_ADMIN_PASSWORD)
    response = JSONResponse({})
    set_cookie(
        response,
        request,
        admin_cookie_name(request),
        issue_admin_token(),
        ADMIN_SESSION_SECONDS,
    )
    return response


@router.get("/session")
async def who_am_i(request: Request) -> Response:
    """Whether this browser is signed in as admin: 200 `{}` or 401."""
    if admin_signed_in(request):
        return JSONResponse({})
    response = error_response(401, "admin_required")
    if admin_cookie_name(request) in request.cookies:
        # An expired, forged or old-password cookie is useless; drop it.
        clear_cookie(response, request, admin_cookie_name(request))
    return response


@router.delete("/session")
async def sign_out(request: Request) -> Response:
    response = Response(status_code=204)
    clear_cookie(response, request, admin_cookie_name(request))
    return response


def _room(details: dict[str, Any]) -> dict[str, str]:
    return {"slug": details["slug"], "name": details["name"]}


@admin_only.get("/rooms")
async def rooms() -> dict[str, Any]:
    """Every room, by name ignoring case (the overview order)."""
    found = await run_in_threadpool(get_rooms)
    return {"rooms": [_room(room) for room in found]}


@admin_only.post("/rooms")
async def new_room(body: JsonBody) -> dict[str, Any]:
    data = parse_body(CreateRoomBody, body)

    def create() -> dict[str, Any] | None:
        check_new_room_password(data.password)
        _room_id, slug = create_room(data.name, data.password)
        return get_room_details_by_slug(slug)

    try:
        details = await run_in_threadpool(create)
    except ValueError as error:
        # Texts: "Room name cannot be empty", "Password cannot be empty".
        raise ApiError(422, "invalid_request", str(error)) from None
    if details is None:  # Deleted again before we read it back.
        raise ApiError(404, "room_unavailable")
    return {"room": _room(details)}


@admin_only.post("/rooms/{slug}/password")
async def reset_password(
    slug: str,
    background: BackgroundTasks,
    body: JsonBody,
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
