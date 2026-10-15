"""A room token authorizes exactly one room, and only while it is current.

Ported from the NiceGUI-only tests of `RoomAccess` and the admin page: the API
uses `validate_room_access_token` for every room request, so the rule is
tested there. An admin sign-in never takes part (tests/test_api_admin.py).
"""

import pytest
from api_helpers import (
    delete_room,
    update_room_password,
    validate_room_access_token,
)

from database_crud import authenticate_room_and_issue_token, create_room


@pytest.mark.parametrize(
    "token_kind", ["missing", "empty", "invalid", "valid", "revoked", "other-room"]
)
def test_only_a_current_token_of_this_room_is_valid(token_kind):
    room_id, slug = create_room("Private room", "password")
    token = None
    if token_kind == "empty":
        token = ""
    elif token_kind == "invalid":
        token = "invalid-token"
    elif token_kind in {"valid", "revoked"}:
        token = authenticate_room_and_issue_token(slug, "password")[1]
        if token_kind == "revoked":
            update_room_password(room_id, "replacement")
    elif token_kind == "other-room":
        _, other_slug = create_room("Other room", "password")
        token = authenticate_room_and_issue_token(other_slug, "password")[1]

    expected = room_id if token_kind == "valid" else None
    assert validate_room_access_token(slug, token) == expected


def test_a_token_stops_working_after_another_device_resets_the_password():
    room_id, slug = create_room("Shared room", "old-password")
    token = authenticate_room_and_issue_token(slug, "old-password")[1]

    assert validate_room_access_token(slug, token) == room_id
    update_room_password(room_id, "new-password")
    assert validate_room_access_token(slug, token) is None
    new_token = authenticate_room_and_issue_token(slug, "new-password")[1]
    assert validate_room_access_token(slug, new_token) == room_id


def test_a_token_does_not_work_for_a_room_that_is_gone():
    room_id, slug = create_room("Short-lived", "password")
    token = authenticate_room_and_issue_token(slug, "password")[1]
    assert validate_room_access_token(slug, token) == room_id

    delete_room(room_id)
    assert validate_room_access_token(slug, token) is None
