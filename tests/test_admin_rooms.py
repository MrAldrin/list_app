import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from nicegui import Client, core, ui
from nicegui.page import page

import main
from database_crud import (
    authenticate_room_and_issue_token,
    create_room,
    delete_room,
    validate_room_access_token,
    verify_room,
)
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


def invoke_button(button):
    async def click():
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(core, "loop", asyncio.get_running_loop())
            next(iter(button._event_listeners.values())).handler(None)
            await asyncio.sleep(0)

    asyncio.run(click())


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


@pytest.mark.parametrize("replace_room", [False, True])
def test_admin_reset_dialog_rejects_stale_room_identity(
    admin_storage, monkeypatch, replace_room
):
    db.execute("DELETE FROM lists")
    db.execute("DELETE FROM rooms")
    db.commit()
    room_id, _stale_slug = create_room("Target room", "original-password")
    notify = Mock()
    monkeypatch.setattr(main.ui, "notify", notify)

    with Client(page("/admin")) as client:
        main.room_list_ui()
        key_button = next(
            element
            for element in client.elements.values()
            if isinstance(element, ui.button) and element._props.get("icon") == "key"
        )
        next(iter(key_button._event_listeners.values())).handler(None)
        password_input = next(
            element
            for element in client.elements.values()
            if isinstance(element, ui.input)
        )
        password_input.value = "stale-reset-password"
        reset_button = next(
            element
            for element in client.elements.values()
            if isinstance(element, ui.button) and element.text == "Reset"
        )

        delete_room(room_id)
        replacement_token = None
        replacement_slug = None
        replacement_before = None
        replacement_tokens = None
        if replace_room:
            replacement_id, replacement_slug = create_room(
                "Replacement room", "replacement-password"
            )
            assert replacement_id == room_id
            replacement_token = authenticate_room_and_issue_token(
                replacement_slug, "replacement-password"
            )[1]
            replacement_before = db.execute(
                "SELECT password_hash, authorization_version FROM rooms WHERE id = ?",
                (replacement_id,),
            ).fetchone()
            replacement_tokens = db.execute(
                "SELECT * FROM room_access_tokens WHERE room_id = ?", (replacement_id,)
            ).fetchall()

        invoke_button(reset_button)

        notify.assert_called_once_with(
            "Room changed or no longer exists; refresh and try again", color="negative"
        )
        if replace_room:
            assert (
                db.execute(
                    "SELECT password_hash, authorization_version FROM rooms WHERE id = ?",
                    (room_id,),
                ).fetchone()
                == replacement_before
            )
            assert (
                db.execute(
                    "SELECT * FROM room_access_tokens WHERE room_id = ?", (room_id,)
                ).fetchall()
                == replacement_tokens
            )
            assert verify_room(replacement_slug, "replacement-password") == room_id
            assert verify_room(replacement_slug, "stale-reset-password") is None
            assert (
                validate_room_access_token(replacement_slug, replacement_token)
                == room_id
            )
        else:
            assert (
                db.execute("SELECT 1 FROM rooms WHERE id = ?", (room_id,)).fetchone()
                is None
            )
        assert admin_storage["authenticated"] is True
        assert not db.in_transaction


def test_reset_dialog_rechecks_admin_authentication(admin_storage, monkeypatch):
    db.execute("DELETE FROM lists")
    db.execute("DELETE FROM rooms")
    db.commit()
    room_id, room_slug = create_room("Target room", "original-password")
    notify = Mock()
    monkeypatch.setattr(main.ui, "notify", notify)

    with Client(page("/admin")) as client:
        main.room_list_ui()
        key_button = next(
            element
            for element in client.elements.values()
            if isinstance(element, ui.button) and element._props.get("icon") == "key"
        )
        next(iter(key_button._event_listeners.values())).handler(None)
        password_input = next(
            element
            for element in client.elements.values()
            if isinstance(element, ui.input)
        )
        password_input.value = "unauthorized-reset"
        reset_button = next(
            element
            for element in client.elements.values()
            if isinstance(element, ui.button) and element.text == "Reset"
        )
        admin_storage["authenticated"] = False

        invoke_button(reset_button)

        notify.assert_called_once_with("Admin sign-in required", color="negative")
        assert verify_room(room_slug, "original-password") == room_id
        assert verify_room(room_slug, "unauthorized-reset") is None
        assert not db.in_transaction


def test_refresh_rechecks_admin_authentication(admin_storage, monkeypatch):
    with Client(page("/admin")) as client:
        main.room_list_ui()
        admin_storage["authenticated"] = False
        query = Mock()
        monkeypatch.setattr(main, "get_rooms", query)
        refresh_rooms(client)
        query.assert_not_called()
        assert not button_texts(client)
