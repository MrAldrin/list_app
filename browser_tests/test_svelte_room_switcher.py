"""Svelte room menu: the Rooms list of rooms this browser entered. One tap
switches rooms; a room without a valid token asks for its password.
"""

import hashlib
import re

from playwright.sync_api import expect
from svelte_app import PHONE, admin_sign_in, app_url, room_app_url, sign_in

CABIN_PASSWORD = "cabin-room-password"


def create_room_as_admin(owner, server, name: str, password: str) -> str:
    owner.goto(app_url(server, "admin"))
    admin_sign_in(owner, server)
    owner.get_by_role("button", name="Create New Room").click()
    owner.get_by_label("Room name").fill(name)
    owner.get_by_label("Password", exact=True).fill(password)
    owner.get_by_label("Password", exact=True).press("Enter")
    expect(owner.get_by_text("Room created")).to_be_visible()
    return server.query("SELECT slug FROM rooms WHERE name = ?", (name,))[0][0]


def test_room_menu_switches_between_remembered_rooms(svelte_server, open_session):
    server = svelte_server
    owner = open_session("owner", **PHONE)
    cabin_slug = create_room_as_admin(owner, server, "Cabin", CABIN_PASSWORD)
    cabin_url = app_url(server, f"room/{cabin_slug}")
    page = open_session("phone", **PHONE)

    # Only Home is entered so far: there is no Rooms list yet.
    sign_in(page, server)
    page.get_by_role("button", name="Room menu").click()
    expect(page.get_by_role("button", name="Share Room")).to_be_visible()
    expect(page.get_by_role("group", name="Rooms")).to_have_count(0)
    page.keyboard.press("Escape")

    # Entering Cabin remembers it; Home is listed from Cabin, not Cabin itself.
    page.goto(cabin_url)
    page.get_by_label("Room Password").fill(CABIN_PASSWORD)
    page.get_by_label("Room Password").press("Enter")
    expect(page.get_by_role("heading", name="Cabin")).to_be_visible()
    page.get_by_role("button", name="Room menu").click()
    expect(page.get_by_role("group", name="Rooms").get_by_role("button")).to_have_text(
        ["Home"]
    )
    page.get_by_role("group", name="Rooms").get_by_role("button", name="Home").click()
    expect(page).to_have_url(re.compile(rf"/room/{server.room_slug}$"))
    expect(page.get_by_role("heading", name="Home")).to_be_visible()

    # One tap back to Cabin.
    page.get_by_role("button", name="Room menu").click()
    expect(page.get_by_role("group", name="Rooms").get_by_role("button")).to_have_text(
        ["Cabin"]
    )
    page.get_by_role("group", name="Rooms").get_by_role("button", name="Cabin").click()
    expect(page).to_have_url(cabin_url)
    expect(page.get_by_role("heading", name="Cabin")).to_be_visible()


def test_switching_to_a_room_without_access_asks_for_its_password(
    svelte_server, open_session
):
    server = svelte_server
    owner = open_session("owner", **PHONE)
    cabin_slug = create_room_as_admin(owner, server, "Cabin", CABIN_PASSWORD)
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    page.goto(app_url(server, f"room/{cabin_slug}"))
    page.get_by_label("Room Password").fill(CABIN_PASSWORD)
    page.get_by_label("Room Password").press("Enter")
    expect(page.get_by_role("heading", name="Cabin")).to_be_visible()

    # Drop Cabin's token (keep the Rooms cookie and Home's sign-in).
    token_name = "listapp-room-" + hashlib.sha256(cabin_slug.encode()).hexdigest()
    kept = [cookie for cookie in page.context.cookies() if cookie["name"] != token_name]
    page.context.clear_cookies()
    page.context.add_cookies(kept)

    page.goto(room_app_url(server))
    expect(page.get_by_role("heading", name="Home")).to_be_visible()
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("group", name="Rooms").get_by_role("button", name="Cabin").click()
    expect(page.get_by_label("Room Password")).to_be_visible()
    page.get_by_label("Room Password").fill(CABIN_PASSWORD)
    page.get_by_label("Room Password").press("Enter")
    expect(page.get_by_role("heading", name="Cabin")).to_be_visible()


def test_logging_out_of_a_room_removes_it_from_the_list(svelte_server, open_session):
    server = svelte_server
    owner = open_session("owner", **PHONE)
    cabin_slug = create_room_as_admin(owner, server, "Cabin", CABIN_PASSWORD)
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    page.goto(app_url(server, f"room/{cabin_slug}"))
    page.get_by_label("Room Password").fill(CABIN_PASSWORD)
    page.get_by_label("Room Password").press("Enter")
    expect(page.get_by_role("heading", name="Cabin")).to_be_visible()

    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Log out").click()
    expect(page.get_by_label("Room Password")).to_be_visible()

    page.goto(room_app_url(server))
    expect(page.get_by_role("heading", name="Home")).to_be_visible()
    page.get_by_role("button", name="Room menu").click()
    expect(page.get_by_role("button", name="Share Room")).to_be_visible()
    expect(page.get_by_role("group", name="Rooms")).to_have_count(0)
