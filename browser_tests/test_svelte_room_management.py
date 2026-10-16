"""Svelte room menu: rename the room, change its password, delete it.

Two phones are signed in to the same room; the second one sees each change.
"""

import re

import pytest
from conftest import wait_for_api_idle
from playwright.sync_api import expect
from svelte_app import (
    PHONE,
    app_url,
    create_list,
    room_app_url,
    sign_in,
    wait_until,
)

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
    wait_for_api_idle(owner)
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


def saved_views(page) -> int:
    """How many saved room views this browser keeps in IndexedDB."""
    return page.evaluate(
        """async () => {
            const db = await new Promise((resolve, reject) => {
                const request = indexedDB.open('listr-snapshots');
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
            const count = await new Promise((resolve, reject) => {
                const request = db.transaction('snapshots').objectStore('snapshots').count();
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
            db.close();
            return count;
        }"""
    )


@pytest.mark.parametrize("server_deletes", [False, True], ids=["not_sent", "delivered"])
def test_reload_during_delete_room_shows_the_server_state(
    svelte_server, open_session, server_deletes
):
    """A reload while the room DELETE is pending shows the server's real state.

    not_sent: the room still exists, so the room opens as before.
    delivered: the server deleted the room, but its answer is lost in the reload;
    the saved view must not stay visible as if the room still existed.
    """
    server = svelte_server
    # Playwright's WebKit ignores page.route for a page the worker controls.
    page = open_session("owner", service_workers="block", **PHONE)
    page.expects_reload_cancel = True  # the reload cancels the held DELETE in WebKit
    held = []

    def hold_first_delete(route):
        if route.request.method != "DELETE" or held:
            route.continue_()
            return
        if server_deletes:
            route.fetch()  # the server deletes the room; the page never gets the answer
        held.append(route)

    page.route(re.compile(r"/api/v1/rooms/[^/]+$"), hold_first_delete)
    sign_in(page, server)
    create_list(page, "Groceries")
    page.goto(room_app_url(server))
    expect(page.get_by_role("link", name="Groceries")).to_be_visible()
    wait_for_api_idle(page)

    open_room_menu(page, "Delete Room")
    page.get_by_label("Enter Room Password to Confirm").fill(server.password)
    page.get_by_role("dialog").get_by_role("button", name="Delete").click()
    wait_until(page, lambda: bool(held), "the room DELETE was not sent", 5_000)
    assert server.query("SELECT COUNT(*) FROM rooms") == [(0 if server_deletes else 1,)]

    page.reload()
    if server_deletes:
        expect(page.get_by_label("Room Password")).to_be_visible()
        expect(page.get_by_role("link", name="Groceries")).to_have_count(0)
        expect(page.get_by_text("Offline — showing", exact=False)).to_have_count(0)
        # The saved view of the deleted room is removed from this browser too.
        wait_until(
            page,
            lambda: saved_views(page) == 0,
            "the saved view of the deleted room was kept",
            10_000,
        )
        page.get_by_label("Room Password").fill(server.password)
        page.get_by_label("Room Password").press("Enter")
        expect(page.get_by_role("alert")).to_have_text("Wrong room or password.")
        expect(page.get_by_role("link", name="Groceries")).to_have_count(0)
    else:
        expect(page.get_by_role("link", name="Groceries")).to_be_visible()
        assert server.query("SELECT name FROM lists") == [("Groceries",)]
