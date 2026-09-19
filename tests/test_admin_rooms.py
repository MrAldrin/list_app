import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from nicegui import Client, core, ui
from nicegui.page import page

import main
from database_setup import db
from room_invitations import create_invitation, create_room_from_invitation


@pytest.fixture
def admin_storage(monkeypatch):
    user = {"authenticated": True}
    monkeypatch.setattr(
        main, "app", SimpleNamespace(storage=SimpleNamespace(user=user))
    )
    yield user
    main.room_list_ui.targets.clear()


def button_texts(client):
    return [e.text for e in client.elements.values() if isinstance(e, ui.button)]


def refresh_rooms(client):
    button = next(
        e
        for e in client.elements.values()
        if isinstance(e, ui.button) and e.text == "Refresh rooms"
    )

    async def click():
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(core, "loop", asyncio.get_running_loop())
            next(iter(button._event_listeners.values())).handler(None)
            await asyncio.sleep(0)

    asyncio.run(click())


@pytest.mark.parametrize("initially_empty", [False, True])
def test_refresh_shows_room_created_after_render(admin_storage, initially_empty):
    if initially_empty:
        db.execute("DELETE FROM lists")
        db.execute("DELETE FROM rooms")
        db.commit()
    _, token = create_invitation()
    with Client(page("/admin")) as client:
        main.room_list_ui()
        create_room_from_invitation(token, "private browser room", "password")
        assert "private browser room" not in button_texts(client)

        refresh_rooms(client)
        assert "private browser room" in button_texts(client)
        refresh_rooms(client)
        assert button_texts(client).count("private browser room") == 1
        assert button_texts(client).count("Refresh rooms") == 1


def test_refresh_rechecks_admin_authentication(admin_storage, monkeypatch):
    with Client(page("/admin")) as client:
        main.room_list_ui()
        admin_storage["authenticated"] = False
        query = Mock()
        monkeypatch.setattr(main, "get_rooms", query)
        refresh_rooms(client)
        query.assert_not_called()
        assert not button_texts(client)
