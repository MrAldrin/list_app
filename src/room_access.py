import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from database_crud import validate_room_access_token


class RoomAccessStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class RoomAccess:
    """Server-side authorization context for one private room page."""

    room_id: int
    room_slug: str
    token: str | None
    admin_requested: bool
    admin_is_authenticated: Callable[[], bool]

    def is_admin(self) -> bool:
        return self.admin_requested and self.admin_is_authenticated()

    def check(self) -> RoomAccessStatus:
        if self.is_admin():
            return RoomAccessStatus.VALID
        if not self.token:
            return RoomAccessStatus.INVALID
        try:
            authorized_room_id = validate_room_access_token(self.room_slug, self.token)
        except (
            sqlite3.Error
        ):  # Database errors must fail closed without clearing storage.
            return RoomAccessStatus.UNAVAILABLE
        if authorized_room_id == self.room_id:
            return RoomAccessStatus.VALID
        return RoomAccessStatus.INVALID
