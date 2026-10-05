"""Room session endpoints: sign in, "who am I", sign out, and the last room.

Cookie rules are in docs/api.md and src/api/access.py. The token lives only in
an HTTP-only cookie; it is never in a response body.
"""

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from api.access import (
    is_https,
    last_room_cookie_name,
    room_access,
    room_cookie_name,
    room_token,
    token_access,
)
from api.errors import ApiError, error_response
from api.requests import json_object, parse_body
from database_crud import (
    authenticate_room_and_issue_token,
    get_room_details_locked,
    revoke_room_access_token,
)
from room_cookies import MAX_AGE

# Longer than any slug the app creates; longer cookie values are ignored.
MAX_SLUG_LENGTH = 256
MAX_PASSWORD_LENGTH = 1024

router = APIRouter()


class SignInBody(BaseModel):
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


def set_cookie(response: Response, request: Request, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=MAX_AGE,
        path="/",
        secure=is_https(request),
        httponly=True,
        samesite="lax",
    )


def clear_cookie(response: Response, request: Request, name: str) -> None:
    # Deleting needs the same Path and Secure flag the cookie was set with.
    response.delete_cookie(
        name,
        path="/",
        secure=is_https(request),
        httponly=True,
        samesite="lax",
    )


@router.post("/rooms/{slug}/session")
def sign_in(
    slug: str, request: Request, body: dict[str, Any] = Depends(json_object)
) -> Response:
    password = parse_body(SignInBody, body).password
    try:
        issued = authenticate_room_and_issue_token(slug, password)
    except sqlite3.Error:
        raise ApiError(503, "unavailable") from None
    if issued is None:
        # Same answer for a wrong password and an unknown room.
        raise ApiError(401, "invalid_password")
    token = issued[1]
    with token_access(slug, token) as room:
        details = get_room_details_locked(room.room_id)
    response = JSONResponse({"room": details})
    set_cookie(response, request, room_cookie_name(request, slug), token)
    set_cookie(response, request, last_room_cookie_name(request), slug)
    return response


@router.get("/rooms/{slug}/session")
def who_am_i(slug: str, request: Request) -> Response:
    try:
        with room_access(request, slug) as room:
            details = get_room_details_locked(room.room_id)
    except ApiError as error:
        if error.status != 401:
            raise
        response = error_response(error.status, error.code, error.message)
        if room_cookie_name(request, slug) in request.cookies:
            # A revoked or expired token is useless; drop it from the browser.
            clear_cookie(response, request, room_cookie_name(request, slug))
        return response
    return JSONResponse({"room": details})


@router.delete("/rooms/{slug}/session")
def sign_out(slug: str, request: Request) -> Response:
    token = room_token(request, slug)
    if token is not None:
        try:
            revoke_room_access_token(slug, token)
        except sqlite3.Error:
            # Keep the cookie so the client can retry; the token is still live.
            raise ApiError(503, "unavailable") from None
    response = Response(status_code=204)
    clear_cookie(response, request, room_cookie_name(request, slug))
    return response


@router.get("/last-room")
def last_room(request: Request) -> dict[str, str | None]:
    """Routing only: the last room this browser signed in to, not access."""
    slug = request.cookies.get(last_room_cookie_name(request))
    if not slug or len(slug) > MAX_SLUG_LENGTH:
        slug = None
    return {"slug": slug}
