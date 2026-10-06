"""Room management with the room password: change it, delete the room.

These are not ops (`POST …/ops`): ops store their request hash and result
for retries, and a password must never be stored, not even hashed that way.
They are online-only actions. Each one needs room access (the cookie) and the
current password, checked in the same write transaction.Rename is an op (`room.rename` in `api/ops.py`).
"""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from api.access import last_room_cookie_name, room_access, room_cookie_name
from api.errors import ApiError
from api.requests import json_object, parse_body
from api.session import MAX_PASSWORD_LENGTH, clear_cookie, set_cookie
from database_crud import (
    change_room_password_locked,
    check_new_room_password,
    delete_room_with_password_locked,
    get_room_details_locked,
)
from live_updates import wake_streams

router = APIRouter()

# Messages shown to the user.
WRONG_CURRENT_PASSWORD = "Incorrect current password"
WRONG_PASSWORD = "Incorrect password"


class ChangePasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: StrictStr = Field(max_length=MAX_PASSWORD_LENGTH)
    new_password: StrictStr = Field(max_length=MAX_PASSWORD_LENGTH)


class DeleteRoomBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: StrictStr = Field(max_length=MAX_PASSWORD_LENGTH)


@router.post("/rooms/{slug}/password")
def change_password(
    slug: str,
    request: Request,
    background: BackgroundTasks,
    body: dict[str, Any] = Depends(json_object),
) -> Response:
    data = parse_body(ChangePasswordBody, body)
    try:
        check_new_room_password(data.new_password)
    except ValueError as error:
        raise ApiError(422, "invalid_request", str(error)) from None
    with room_access(request, slug, write=True) as room:
        token = change_room_password_locked(
            room.room_id, data.current_password, data.new_password
        )
        if token is None:
            raise ApiError(403, "wrong_password", WRONG_CURRENT_PASSWORD)
        details = get_room_details_locked(room.room_id)
    response = JSONResponse({"room": details})
    set_cookie(response, request, room_cookie_name(request, slug), token)
    set_cookie(response, request, last_room_cookie_name(request), slug)
    # Old tokens are revoked: the room's other streams close. Woken after the
    # response is sent, so this browser has the new cookie before its own
    # stream asks "who am I".
    background.add_task(wake_streams, room.room_id)
    return response


@router.delete("/rooms/{slug}")
def delete_room(
    slug: str,
    request: Request,
    background: BackgroundTasks,
    body: dict[str, Any] = Depends(json_object),
) -> Response:
    password = parse_body(DeleteRoomBody, body).password
    with room_access(request, slug, write=True) as room:
        if not delete_room_with_password_locked(room.room_id, password):
            raise ApiError(403, "wrong_password", WRONG_PASSWORD)
    response = Response(status_code=204)
    clear_cookie(response, request, room_cookie_name(request, slug))
    if request.cookies.get(last_room_cookie_name(request)) == slug:
        clear_cookie(response, request, last_room_cookie_name(request))
    # The room's streams find no access and send `revoked`.
    background.add_task(wake_streams, room.room_id)
    return response
