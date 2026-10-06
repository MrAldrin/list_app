"""Svelte room menu: rename the room, change its password, delete it.

Two phones are signed in to the same room; the second one sees each change.
"""

import re

from playwright.sync_api import expect
from svelte_app import PHONE, app_url, create_list, sign_in

NEW_PASSWORD = "a-new-room-password"


def open_room_menu(page, entry: str) -> None:
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name=entry).click()


def test_rename_change_password_and_delete_room(svelte_server, open_session):
    server = svelte_server
    slug = server.room_slug
    room_url = app_url(server, f"room/{slug}")
    owner = open_session("owner", **PHONE)
    other = open_session("other", **PHONE)
    sign_in(owner, server)
    sign_in(other, server)

    # Rename: a blank name is refused and the dialog stays open.
    open_room_menu(owner, "Rename Room")
    expect(owner.get_by_label("New name")).to_have_value("Home")
    owner.get_by_label("New name").fill("  ")
    owner.get_by_label("New name").press("Enter")
    expect(owner.get_by_text("Name cannot be empty")).to_be_visible()
    owner.get_by_label("New name").fill("  Our Cabin ")
    owner.get_by_role("button", name="Save").click()
    expect(owner.get_by_role("dialog")).to_have_count(0)
    expect(owner.get_by_role("heading", name="Our Cabin")).to_be_visible()
    expect(other.get_by_role("heading", name="Our Cabin")).to_be_visible()
    assert server.query("SELECT name, slug FROM rooms") == [("Our Cabin", slug)]

    # Change password: a wrong current password changes nothing.
    open_room_menu(owner, "Change Password")
    owner.get_by_label("Current Password").fill("wrong")
    owner.get_by_label("New Password").fill(NEW_PASSWORD)
    owner.get_by_role("button", name="Change").click()
    expect(owner.get_by_text("Incorrect current password")).to_be_visible()
    owner.get_by_label("Current Password").fill(server.password)
    owner.get_by_role("button", name="Change").click()
    expect(owner.get_by_text("Password changed successfully")).to_be_visible()
    expect(owner.get_by_role("dialog")).to_have_count(0)

    # This phone stays signed in; the other one must sign in again.
    expect(other.get_by_label("Room Password")).to_be_visible()
    create_list(owner, "Groceries")
    owner.goto(room_url)
    expect(owner.get_by_role("link", name="Groceries")).to_be_visible()
    other.get_by_label("Room Password").fill(server.password)
    other.get_by_label("Room Password").press("Enter")
    expect(other.get_by_role("alert")).to_have_text("Wrong room or password.")
    other.get_by_label("Room Password").fill(NEW_PASSWORD)
    other.get_by_label("Room Password").press("Enter")
    expect(other.get_by_role("link", name="Groceries")).to_be_visible()

    # Delete: Cancel keeps the room; a wrong password changes nothing.
    open_room_menu(owner, "Delete Room")
    expect(
        owner.get_by_text("This will delete ALL lists and items inside this room.")
    ).to_be_visible()
    owner.get_by_role("button", name="Cancel").click()
    open_room_menu(owner, "Delete Room")
    owner.get_by_label("Enter Room Password to Confirm").fill(server.password)
    owner.get_by_role("dialog").get_by_role("button", name="Delete").click()
    expect(owner.get_by_text("Incorrect password")).to_be_visible()
    assert server.query("SELECT COUNT(*) FROM rooms") == [(1,)]

    owner.get_by_label("Enter Room Password to Confirm").fill(NEW_PASSWORD)
    owner.get_by_role("dialog").get_by_role("button", name="Delete").click()
    expect(owner.get_by_text("Room deleted")).to_be_visible()
    expect(owner).to_have_url(re.compile(r"/$"))
    expect(owner.get_by_text("Open your room link to continue")).to_be_visible()
    assert server.query("SELECT COUNT(*) FROM rooms") == [(0,)]
    assert server.query("SELECT COUNT(*) FROM lists") == [(0,)]

    # The other phone is signed out; the room is gone like a wrong password.
    expect(other.get_by_label("Room Password")).to_be_visible()
    other.get_by_label("Room Password").fill(NEW_PASSWORD)
    other.get_by_label("Room Password").press("Enter")
    expect(other.get_by_role("alert")).to_have_text("Wrong room or password.")
