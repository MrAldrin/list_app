"""Sign-in rate limit for the API: which buckets an attempt uses, and the 429 answer.

The limiter itself is in src/sign_in_limiter.py. Limits: see docs/api.md
("Sign-in limit").
"""

from collections.abc import Hashable

from fastapi import Request
from fastapi.responses import Response

from api.errors import error_response
from sign_in_limiter import (
    ADMIN_LIMIT,
    CLIENT_LIMIT,
    ROOM_LIMIT,
    Reservation,
    SignInLimiter,
)

sign_in_limiter = SignInLimiter()


def client_address(request: Request) -> str:
    """The client address as uvicorn reports it (see docs/api.md, "Sign-in limit")."""
    return request.client.host if request.client else "unknown"


def reserve_room_sign_in(request: Request, slug: str) -> Reservation | Response:
    """One slot for a room sign-in attempt, or the 429 answer."""
    return _reserve(
        [
            (("room", slug), ROOM_LIMIT),
            (("client", client_address(request)), CLIENT_LIMIT),
        ]
    )


def reserve_admin_sign_in(request: Request) -> Reservation | Response:
    """One slot for an admin sign-in attempt, or the 429 answer."""
    return _reserve(
        [(("admin",), ADMIN_LIMIT), (("client", client_address(request)), CLIENT_LIMIT)]
    )


def release(reservation: Reservation) -> None:
    """Call after a successful sign-in: its attempt does not count."""
    sign_in_limiter.release(reservation)


def _reserve(limits: list[tuple[Hashable, int]]) -> Reservation | Response:
    taken = sign_in_limiter.reserve(limits)
    if isinstance(taken, Reservation):
        return taken
    return error_response(
        429,
        "too_many_attempts",
        headers={"Retry-After": str(taken)},
    )
