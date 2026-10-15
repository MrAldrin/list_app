"""Set and clear the API's cookies. The security flags are defined only here.

Every cookie is HttpOnly, SameSite=Lax and Path=/. Secure is on only over HTTPS.
The names and lifetimes are set by the callers: room cookies in
src/room_cookies.py and src/api/access.py, admin cookies in src/api/admin.py.
"""

from fastapi import Request
from fastapi.responses import Response

from api.access import is_https, last_room_cookie_name, room_cookie_name
from room_cookies import MAX_AGE


def set_cookie(
    response: Response, request: Request, name: str, value: str, max_age: int
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
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


def set_room_cookies(
    response: Response, request: Request, slug: str, token: str
) -> None:
    """Set the room's token cookie and the last-room cookie that routes the app."""
    set_cookie(response, request, room_cookie_name(request, slug), token, MAX_AGE)
    set_cookie(response, request, last_room_cookie_name(request), slug, MAX_AGE)
