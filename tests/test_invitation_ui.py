import pytest
from nicegui import Client, ui
from nicegui.page import page

import room_invitations
from database_crud import get_rooms, verify_room
from room_invitations import (
    create_invitation,
    get_invitations,
    invitation_is_active,
    revoke_invitation,
)
from ui.room_invitations import creation_form, invitation_controls


def elements(client, kind):
    return [e for e in client.elements.values() if isinstance(e, kind)]


def click(client, text):
    button = next(e for e in elements(client, ui.button) if e.text == text)
    next(iter(button._event_listeners.values())).handler(None)


def fill(client, name="My room", password="my-password", confirmation="my-password"):
    for element, value in zip(
        elements(client, ui.input), (name, password, confirmation), strict=True
    ):
        element.value = value


def test_creation_and_duplicate_submit(monkeypatch):
    _, token = create_invitation()
    destinations = []
    monkeypatch.setattr(ui.navigate, "to", destinations.append)
    with Client(page("/")) as client:
        creation_form(token)
        fill(client)
        before = len(get_rooms())
        click(client, "Create room")
        click(client, "Create room")
        assert len(get_rooms()) == before + 1
        assert len(destinations) == 1
        assert destinations[0].startswith("/room/")
        assert "admin" not in destinations[0]
        assert verify_room(destinations[0].removeprefix("/room/"), "my-password")
        assert all(e.value == "" for e in elements(client, ui.input)[1:])


def test_invalid_link_does_not_render_form():
    with Client(page("/")) as client:
        creation_form("invalid")
        assert not elements(client, ui.input)
        assert not elements(client, ui.button)


def test_password_mismatch_does_not_create_room():
    _, token = create_invitation()
    with Client(page("/")) as client:
        creation_form(token)
        fill(client, confirmation="different")
        before = get_rooms()
        click(client, "Create room")
        assert get_rooms() == before


@pytest.mark.parametrize("invalidate", ["revoke", "expire"])
def test_invalidated_link_after_page_load_blocks_submit(monkeypatch, invalidate):
    invitation_id, token = create_invitation()
    with Client(page("/")) as client:
        creation_form(token)
        fill(client)
        if invalidate == "revoke":
            revoke_invitation(invitation_id)
        else:
            expiry = get_invitations()[0]["expires_at"]
            monkeypatch.setattr(room_invitations.time, "time", lambda: expiry)
        before = get_rooms()
        click(client, "Create room")
        assert get_rooms() == before
        assert not elements(client, ui.button)[0].enabled


def test_admin_controls_are_hidden_without_authentication():
    with Client(page("/")) as client:
        invitation_controls(lambda: False, "https://example.test/")
        assert not elements(client, ui.button)
        assert get_invitations() == []


def test_admin_generate_rechecks_authentication():
    authenticated = True
    with Client(page("/")) as client:
        invitation_controls(lambda: authenticated, "https://example.test/")
        authenticated = False
        click(client, "Generate 7-day invitation")
        assert get_invitations() == []


def test_admin_can_generate_full_link_and_revoke(monkeypatch):
    monkeypatch.setattr(room_invitations.time, "time", lambda: 0)
    authenticated = True
    with Client(page("/")) as client:
        invitation_controls(lambda: authenticated, "https://example.test/")
        click(client, "Generate 7-day invitation")
        labels = [element.text for element in elements(client, ui.label)]
        assert "Created 1970-01-01 00:00 UTC" in labels
        assert "Expires 1970-01-08 00:00 UTC" in labels
        link = elements(client, ui.input)[0].value
        assert link.startswith("https://example.test/create-room/")
        token = link.rsplit("/", 1)[1]
        assert invitation_is_active(token)
        authenticated = False
        click(client, "Revoke")
        assert invitation_is_active(token)
        authenticated = True
        click(client, "Revoke")
        assert not invitation_is_active(token)
