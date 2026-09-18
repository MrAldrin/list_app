import sqlite3
from unittest.mock import patch

from database_crud import (
    authenticate_room_and_issue_token,
    create_room,
    update_room_password,
)
from room_access import RoomAccess, RoomAccessStatus


def test_open_room_access_is_denied_after_another_device_resets_password():
    room_id, room_slug = create_room("Shared room", "old-password")
    token = authenticate_room_and_issue_token(room_slug, "old-password")[1]
    open_page_access = RoomAccess(
        room_id=room_id,
        room_slug=room_slug,
        token=token,
        admin_requested=False,
        admin_is_authenticated=lambda: False,
    )

    assert open_page_access.check() is RoomAccessStatus.VALID
    update_room_password(room_id, "new-password")
    assert open_page_access.check() is RoomAccessStatus.INVALID


def test_authenticated_admin_must_use_the_explicit_admin_room_path():
    room_id, room_slug = create_room("Admin room", "password")

    implicit_admin_access = RoomAccess(
        room_id=room_id,
        room_slug=room_slug,
        token=None,
        admin_requested=False,
        admin_is_authenticated=lambda: True,
    )
    explicit_admin_access = RoomAccess(
        room_id=room_id,
        room_slug=room_slug,
        token=None,
        admin_requested=True,
        admin_is_authenticated=lambda: True,
    )

    assert implicit_admin_access.check() is RoomAccessStatus.INVALID
    assert explicit_admin_access.check() is RoomAccessStatus.VALID


def test_database_failure_denies_access_without_calling_it_invalid():
    access = RoomAccess(
        room_id=1,
        room_slug="room",
        token="token",
        admin_requested=False,
        admin_is_authenticated=lambda: False,
    )

    with patch(
        "room_access.validate_room_access_token",
        side_effect=sqlite3.OperationalError("database unavailable"),
    ):
        assert access.check() is RoomAccessStatus.UNAVAILABLE
