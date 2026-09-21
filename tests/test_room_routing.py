import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from nicegui import Client, ui
from nicegui.page import page

import main
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
