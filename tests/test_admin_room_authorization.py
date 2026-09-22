"""Admin sessions and admin query parameters must never unlock private rooms."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import main
from database_crud import (
    authenticate_room_and_issue_token,
    create_room,
    update_room_password,
)
from room_access import RoomAccess, RoomAccessStatus


@pytest.mark.parametrize("admin_requested", [False, True])
@pytest.mark.parametrize(
    "token_kind", ["missing", "invalid", "valid", "revoked", "other-room"]
)
def test_admin_browser_requires_valid_room_token(
    monkeypatch, admin_requested, token_kind
):
    room_id, slug = create_room("Private room", "password")
    token = None
    if token_kind == "invalid":
        token = "invalid-token"
    elif token_kind in {"valid", "revoked"}:
        token = authenticate_room_and_issue_token(slug, "password")[1]
        if token_kind == "revoked":
            update_room_password(room_id, "replacement")
    elif token_kind == "other-room":
        _, other_slug = create_room("Other room", "password")
        token = authenticate_room_and_issue_token(other_slug, "password")[1]

    monkeypatch.setattr(
        main,
        "app",
        SimpleNamespace(storage=SimpleNamespace(user={"authenticated": True})),
    )
    monkeypatch.setattr(main, "_cleanup_legacy_room_password_keys", AsyncMock())
    lookup = AsyncMock(return_value=(True, token))
    monkeypatch.setattr(main, "_get_browser_storage", lookup)
    monkeypatch.setattr(main, "_remember_authorized_room", Mock())
    monkeypatch.setattr(main, "_forget_authorized_room", Mock())
    monkeypatch.setattr(main, "_remove_room_token", AsyncMock())

    expected = (
        RoomAccessStatus.VALID if token_kind == "valid" else RoomAccessStatus.INVALID
    )
    # Check both the page's browser lookup and authorization used by callbacks.
    access, status = asyncio.run(
        main._room_access_from_browser(room_id, slug, admin_requested)
    )
    assert status is expected
    assert access.check() is expected
    lookup.assert_awaited_once()
    assert (
        RoomAccess(room_id, slug, token, admin_requested, lambda: True).check()
        is expected
    )
