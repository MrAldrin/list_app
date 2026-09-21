import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from nicegui import Client, ui
from nicegui.page import page

import main
from database_crud import authenticate_room_and_issue_token, update_room_password
from database_setup import db


@pytest.fixture
def routing(monkeypatch):
    user = {}
    monkeypatch.setattr(
        main, "app", SimpleNamespace(storage=SimpleNamespace(user=user))
    )
    monkeypatch.setattr(main, "_cleanup_legacy_room_password_keys", AsyncMock())
    storage = AsyncMock(return_value=(True, None))
    monkeypatch.setattr(main, "_get_browser_storage", storage)
    navigate = Mock()
    monkeypatch.setattr(main.ui.navigate, "to", navigate)
    notify = Mock()
    monkeypatch.setattr(main.ui, "notify", notify)
    slug = db.execute("SELECT slug FROM rooms").fetchone()[0]
    return SimpleNamespace(slug=slug, storage=storage, navigate=navigate, notify=notify)


def render_index(client):
    async def render():
        with client:
            await main.index()

    asyncio.run(render())


@pytest.mark.parametrize(
    "template",
    [
        "{slug}",
        "https://example.com/room/{slug}",
        "https://example.com/room/{slug}?admin=true",
        "https://example.com/room/{slug}?",
        "https://example.com/room/{slug}#section",
        "  https://example.com/room/{slug}/?admin=true#section  ",
        "/room/{slug}?admin=true",
    ],
)
def test_pasted_room_link(routing, template):
    with Client(page("/")) as client:
        render_index(client)
        field = next(e for e in client.elements.values() if isinstance(e, ui.input))
        field.value = template.format(slug=routing.slug)
        button = next(
            e
            for e in client.elements.values()
            if isinstance(e, ui.button) and e.text == "Open Room"
        )
        next(iter(button._event_listeners.values())).handler(None)
        routing.navigate.assert_called_once_with(f"/room/{routing.slug}")


@pytest.mark.parametrize("value", ["", "unknown-room", "https://[broken/room/foo"])
def test_invalid_room_link_does_not_navigate(routing, value):
    with Client(page("/")) as client:
        render_index(client)
        field = next(e for e in client.elements.values() if isinstance(e, ui.input))
        field.value = value
        button = next(
            e
            for e in client.elements.values()
            if isinstance(e, ui.button) and e.text == "Open Room"
        )
        next(iter(button._event_listeners.values())).handler(None)
        routing.navigate.assert_not_called()
        routing.notify.assert_called_once()


@pytest.mark.parametrize("login", ["missing", "revoked", "valid"])
def test_remembered_room_opens_even_without_valid_login(routing, monkeypatch, login):
    token = None
    if login != "missing":
        room_id, token = authenticate_room_and_issue_token(routing.slug, "pw")
        if login == "revoked":
            update_room_password(room_id, "new-password")
    routing.storage.side_effect = [(True, routing.slug), (True, token)]
    remove = AsyncMock()
    monkeypatch.setattr(main, "_remove_room_token", remove)
    with Client(page("/")) as client:
        render_index(client)
        routing.navigate.assert_called_once_with(f"/room/{routing.slug}")
        assert not any(isinstance(e, ui.input) for e in client.elements.values())
    if login == "revoked":
        remove.assert_awaited_once_with(routing.slug)
    else:
        remove.assert_not_awaited()

    if login != "valid":
        routing.storage.side_effect = None
        routing.storage.return_value = (True, None)

        async def open_room():
            with Client(page("/room/{slug}")) as client:
                await main.room_page(routing.slug)
                assert any(
                    isinstance(e, ui.label) and "Enter Room Password" in e.text
                    for e in client.elements.values()
                )

        asyncio.run(open_room())


@pytest.mark.parametrize(
    "case", ["deleted", "storage-unavailable", "database-unavailable"]
)
def test_unrecoverable_room_keeps_fallback_and_saved_access(routing, monkeypatch, case):
    remove = AsyncMock()
    monkeypatch.setattr(main, "_remove_room_token", remove)
    if case == "deleted":
        routing.storage.return_value = (True, "deleted-room")
    elif case == "storage-unavailable":
        routing.storage.side_effect = [(True, routing.slug), (False, None)]
    else:
        routing.storage.side_effect = [(True, routing.slug), (True, "saved-token")]
        monkeypatch.setattr(
            main.RoomAccess, "check", lambda self: main.RoomAccessStatus.UNAVAILABLE
        )
    with Client(page("/")) as client:
        render_index(client)
        assert any(isinstance(e, ui.input) for e in client.elements.values())
    routing.navigate.assert_not_called()
    remove.assert_not_awaited()
