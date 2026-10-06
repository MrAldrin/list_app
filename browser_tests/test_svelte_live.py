"""Svelte live updates: two phones, NiceGUI side by side, deletes and revoked access."""

import re

import pytest
from playwright.sync_api import expect
from svelte_app import (
    DESKTOP,
    PHONE,
    add_item,
    create_list,
    item_names,
    nicegui_sign_in,
    room_app_url,
    sign_in,
)


def test_two_phones_see_each_others_changes(svelte_server, open_session):
    server = svelte_server
    phone_a = open_session("phone-a", **PHONE)
    phone_b = open_session("phone-b", **PHONE)
    sign_in(phone_a, server)
    sign_in(phone_b, server)

    # A new list appears on the other phone's room page.
    list_url = create_list(phone_b, "Groceries")
    phone_a.get_by_role("link", name="Groceries").click()
    expect(phone_a).to_have_url(list_url)

    # Items, checks and tags go both ways.
    add_item(phone_b, "milk")
    expect(item_names(phone_a)).to_have_text(["milk"])
    phone_a.get_by_role("checkbox", name="milk").check()
    expect(phone_b.get_by_role("checkbox", name="milk")).to_be_checked()
    phone_a.get_by_role("button", name="Options").click()
    phone_a.get_by_label("Add Tag").fill("Lidl")
    phone_a.get_by_label("Add Tag").press("Enter")
    expect(phone_b.get_by_role("button", name="Lidl tag for milk")).to_be_visible()

    # A list rename shows on the open list page.
    phone_b.goto(room_app_url(server))
    phone_b.get_by_role("button", name="Rename Groceries").click()
    phone_b.get_by_label("List Name").fill("Food")
    phone_b.get_by_label("List Name").press("Enter")
    expect(phone_a.get_by_role("heading", name="Food")).to_be_visible()


@pytest.mark.skip(
    reason="Retired in 4.3/4.4: tests live sync between the NiceGUI page and Svelte; step 4.2 moved Svelte to / and NiceGUI's pages are no longer reachable"
)
def test_nicegui_and_svelte_see_each_others_changes(svelte_server, open_session):
    server = svelte_server
    phone = open_session("phone", **PHONE)
    desktop = open_session("nicegui", **DESKTOP)
    sign_in(phone, server)
    create_list(phone, "Groceries")
    add_item(phone, "milk")
    list_slug = phone.url.rsplit("/", 1)[1]

    # NiceGUI needs its own sign-in: on plain HTTP it keeps access elsewhere.
    nicegui_sign_in(desktop, server)
    desktop.goto(f"{server.url}/list/{list_slug}")
    expect(desktop.get_by_text("milk", exact=True)).to_be_visible()

    # NiceGUI -> Svelte.
    desktop.get_by_label("Add or Search", exact=True).fill("eggs")
    desktop.get_by_label("Add or Search", exact=True).press("Enter")
    expect(item_names(phone)).to_have_text(["eggs", "milk"])

    # Svelte -> NiceGUI.
    phone.get_by_role("checkbox", name="milk").check()
    expect(desktop.get_by_text("milk", exact=True)).to_have_class(
        re.compile("line-through")
    )


def test_list_deleted_while_open(svelte_server, open_session):
    server = svelte_server
    viewer = open_session("viewer", **PHONE)
    deleter = open_session("deleter", **PHONE)
    sign_in(viewer, server)
    create_list(viewer, "Groceries")
    add_item(viewer, "milk")
    sign_in(deleter, server)

    deleter.get_by_role("button", name="Delete Groceries").click()
    deleter.get_by_role("dialog").get_by_role("button", name="Delete").click()
    expect(viewer.get_by_text("This list was deleted.")).to_be_visible()
    viewer.get_by_role("link", name="Back to room").click()
    expect(viewer).to_have_url(room_app_url(server))
    expect(viewer.get_by_text("No lists yet. Create your first one!")).to_be_visible()


def test_password_change_revokes_open_pages(svelte_server, open_session):
    server = svelte_server
    room_page = open_session("room-page", **PHONE)
    list_page = open_session("list-page", **PHONE)
    desktop = open_session("nicegui", **DESKTOP)
    sign_in(room_page, server)
    create_list(room_page, "Groceries")
    room_page.go_back()
    sign_in(list_page, server)
    list_page.get_by_role("link", name="Groceries").click()
    expect(list_page.get_by_role("heading", name="Groceries")).to_be_visible()

    # Change the password in NiceGUI: both open Svelte pages lose access live.
    nicegui_sign_in(desktop, server)
    desktop.get_by_role("button", name="Room menu").click()
    desktop.get_by_text("Change Password").click()
    desktop.get_by_label("Current Password").fill(server.password)
    desktop.get_by_label("New Password").fill("new-room-password")
    desktop.get_by_role("button", name="Change").click()
    expect(room_page.get_by_label("Room Password")).to_be_visible()
    expect(list_page.get_by_label("Room Password")).to_be_visible()

    # The old password no longer works; the new one does.
    room_page.get_by_label("Room Password").fill(server.password)
    room_page.get_by_label("Room Password").press("Enter")
    expect(room_page.get_by_role("alert")).to_have_text("Wrong room or password.")
    room_page.get_by_label("Room Password").fill("new-room-password")
    room_page.get_by_label("Room Password").press("Enter")
    expect(room_page.get_by_role("link", name="Groceries")).to_be_visible()


def test_rename_saved_after_a_password_change_changes_nothing(
    svelte_server, open_session
):
    server = svelte_server
    stale = open_session("stale", **PHONE)
    other = open_session("other", **PHONE)
    # The live stream never connects, so the page misses the password change.
    stale.route("**/api/v1/rooms/*/events", lambda route: None)
    sign_in(stale, server)
    create_list(stale, "Groceries")
    stale.goto(room_app_url(server))
    stale.get_by_role("button", name="Rename Groceries").click()
    stale.get_by_label("List Name").fill("forbidden rename")

    sign_in(other, server)
    other.get_by_role("button", name="Room menu").click()
    other.get_by_role("button", name="Change Password").click()
    other.get_by_label("Current Password").fill(server.password)
    other.get_by_label("New Password").fill("new-room-password")
    other.get_by_role("button", name="Change").click()
    expect(other.get_by_text("Password changed successfully")).to_be_visible()

    # Save from the dialog that stayed open: refused, and the page signs out.
    with stale.expect_response(re.compile(r"/api/v1/rooms/.*/ops$")) as answer:
        stale.get_by_role("button", name="Save").click()
    assert answer.value.status == 401
    expect(stale.get_by_label("Room Password")).to_be_visible()
    assert server.query("SELECT name FROM lists") == [("Groceries",)]
