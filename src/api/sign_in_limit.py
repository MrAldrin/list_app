"""Sign-in rate limit for the API: which buckets an attempt uses, and the 429 answer.

The limiter itself is in src/sign_in_limiter.py. Limits: see docs/api.md
("Sign-in limit").
"""

from collections.abc import Hashable

from fastapi.responses import Response

from api.errors import error_response
from sign_in_limiter import (
    ADMIN_LIMIT,
    ALL_ROOMS_LIMIT,
    ROOM_LIMIT,
    Reservation,
    SignInLimiter,
)

sign_in_limiter = SignInLimiter()


def reserve_room_sign_in(slug: str) -> Reservation | Response:
    """One slot in this room's bucket and one in the all-rooms bucket, or the 429 answer.

    The all-rooms bucket stops random slugs from each getting a fresh limit.
    """
    return _reserve([(("room", slug), ROOM_LIMIT), (("all rooms",), ALL_ROOMS_LIMIT)])


def reserve_admin_sign_in() -> Reservation | Response:
    """One slot for an admin sign-in attempt, or the 429 answer."""
    return _reserve([(("admin",), ADMIN_LIMIT)])


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
