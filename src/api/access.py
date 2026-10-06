"""Room access for API endpoints: room cookies and the access transaction.

On HTTPS the API uses `__Host-` cookies. On plain HTTP (local network tests) browsers refuse
`__Host-` cookies, so the API uses the same names without the prefix and
without `Secure`. Each scheme reads only its own names.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import Request

from api.errors import ApiError
from database_crud import (
    RoomAccessDenied,
    ShareLinkDenied,
    room_token_transaction,
    share_token_transaction,
)
from room_cookies import (
    LAST_ROOM_COOKIE,
    PLAIN_LAST_ROOM_COOKIE,
    plain_token_cookie_name,
    token_cookie_name,
)

# Same limit as NiceGUI's cookie endpoint; issued tokens are 43 characters.
MAX_TOKEN_LENGTH = 256


def is_https(request: Request) -> bool:
    """The scheme as the ASGI server reports it.

    Behind a proxy (Railway), the server rewrites the scheme from trusted
    forwarded headers.
    """
    return request.url.scheme == "https"


def room_cookie_name(request: Request, slug: str) -> str:
    return (
        token_cookie_name(slug) if is_https(request) else plain_token_cookie_name(slug)
    )


def last_room_cookie_name(request: Request) -> str:
    return LAST_ROOM_COOKIE if is_https(request) else PLAIN_LAST_ROOM_COOKIE


def room_token(request: Request, slug: str) -> str | None:
    """The room token from this browser's cookie, or None."""
    token = request.cookies.get(room_cookie_name(request, slug))
    if not token or len(token) > MAX_TOKEN_LENGTH:
        return None
    return token


@dataclass(frozen=True)
class RoomContext:
    """The room an API request may access, valid inside room_access()."""

    room_id: int
    slug: str


@contextmanager
def room_access(
    request: Request, slug: str, *, write: bool = False
) -> Iterator[RoomContext]:
    """Check room access and run the block in the same database transaction.

    Use it for every room read or write:

        with room_access(request, slug, write=True) as room:
            ...  # reads and writes for room.room_id, under the database lock

    Raises ApiError 401 `not_authenticated` without valid access (an unknown
    room looks the same) and 503 `unavailable` on database errors. The
    transaction commits when the block ends and rolls back on any error.
    """
    with token_access(slug, room_token(request, slug), write=write) as room:
        yield room


@contextmanager
def token_access(
    slug: str, token: str | None, *, write: bool = False
) -> Iterator[RoomContext]:
    """Like room_access(), for a token that is not in a cookie yet."""
    if token is None:
        raise ApiError(401, "not_authenticated")
    try:
        with room_token_transaction(slug, token, write=write) as room_id:
            yield RoomContext(room_id=room_id, slug=slug)
    except RoomAccessDenied:
        raise ApiError(401, "not_authenticated") from None
    except sqlite3.Error:
        # Fail closed, but keep the cookie: the access may still be valid.
        raise ApiError(503, "unavailable") from None


@dataclass(frozen=True)
class ShareContext:
    """The one list a share link opens, valid inside share_access().

    `room_id` is for change tracking and stored ops only. A share link never
    gives room access: every read and write is limited to `list_id`.
    """

    room_id: int
    list_id: int


@contextmanager
def share_access(token: str, *, write: bool = False) -> Iterator[ShareContext]:
    """Check a share token and run the block in the same database transaction.

    Raises ApiError 401 `share_unavailable` when the token opens no list
    (never issued, reset, or the list was deleted: they look the same) and
    503 on database errors.
    """
    try:
        with share_token_transaction(token, write=write) as (room_id, list_id):
            yield ShareContext(room_id=room_id, list_id=list_id)
    except ShareLinkDenied:
        raise ApiError(401, "share_unavailable") from None
    except sqlite3.Error:
        raise ApiError(503, "unavailable") from None
