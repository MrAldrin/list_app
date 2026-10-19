"""Svelte room switcher: the room name in the room header opens a panel with
the rooms this browser entered. One tap switches rooms; "+ Add room" opens the
start page without jumping to the last room; a room without a valid token asks
for its password. The room menu (⋮) has no Rooms list.
"""

import hashlib
import re

from playwright.sync_api import expect
from svelte_app import PHONE, admin_sign_in, app_url, room_app_url, sign_in

CABIN_PASSWORD = "cabin-room-password"
LAST_ROOM_API = re.compile(r"/api/v1/last-room$")


def open_switcher(page):
    """Tap the room name in the header: it opens the Rooms panel."""
    page.get_by_role("button", name="Switch room").click()


def room_buttons(page):
    """The other rooms in the Rooms panel: not "+ Add room" and not the current room (✓)."""
    return (
        page.get_by_role("group", name="Rooms")
        .get_by_role("button")
        .filter(has_not_text="Add room")
        .filter(has_not_text="✓")
    )


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

    # Only Home is entered so far: the Rooms panel has the current room and "+ Add room".
    sign_in(page, server)
    open_switcher(page)
    expect(page.get_by_role("group", name="Rooms")).to_be_visible()
    expect(room_buttons(page)).to_have_count(0)
    expect(page.get_by_role("group", name="Rooms").get_by_role("button")).to_have_text(
        ["✓ Home", "+ Add room"]
    )
    page.keyboard.press("Escape")

    # Entering Cabin remembers it; Home is listed from Cabin, not Cabin itself.
    page.goto(cabin_url)
    page.get_by_label("Room Password").fill(CABIN_PASSWORD)
    page.get_by_label("Room Password").press("Enter")
    expect(page.get_by_role("heading", name="Cabin")).to_be_visible()
    open_switcher(page)
    expect(room_buttons(page)).to_have_text(["Home"])
    page.get_by_role("group", name="Rooms").get_by_role("button", name="Home").click()
    expect(page).to_have_url(re.compile(rf"/room/{server.room_slug}$"))
    expect(page.get_by_role("heading", name="Home")).to_be_visible()

    # One tap back to Cabin.
    open_switcher(page)
    expect(room_buttons(page)).to_have_text(["Cabin"])
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
    open_switcher(page)
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
    page.keyboard.press("Escape")
    open_switcher(page)
    expect(room_buttons(page)).to_have_count(0)


def test_add_room_opens_the_start_page_and_both_rooms_link_to_each_other(
    svelte_server, open_session
):
    server = svelte_server
    owner = open_session("owner", **PHONE)
    cabin_slug = create_room_as_admin(owner, server, "Cabin", CABIN_PASSWORD)
    page = open_session("phone", **PHONE)
    sign_in(page, server)  # Home is the last room.

    # "+ Add room" opens the start page. It makes no last-room request, so it
    # does not jump back to Home; Home stays signed in.
    last_room_requests = []

    def record(request):
        if LAST_ROOM_API.search(request.url):
            last_room_requests.append(request.url)

    page.on("request", record)
    open_switcher(page)
    page.get_by_role("group", name="Rooms").get_by_role(
        "button", name="+ Add room"
    ).click()
    expect(page).to_have_url(re.compile(r"/\?add$"))
    expect(page.get_by_role("heading", name="Add a room")).to_be_visible()
    assert last_room_requests == [], last_room_requests

    # Admin is a small link under the room form, not the main button.
    open_button = page.get_by_role("button", name="Open Room")
    admin_button = page.get_by_role("button", name="Admin")
    expect(admin_button).to_be_visible()
    assert admin_button.bounding_box()["y"] > open_button.bounding_box()["y"]

    # A second room, entered by its code, asks for its password, then opens.
    page.get_by_label("Room link or code").fill(cabin_slug)
    page.get_by_role("button", name="Open Room").click()
    page.get_by_label("Room Password").fill(CABIN_PASSWORD)
    page.get_by_label("Room Password").press("Enter")
    expect(page.get_by_role("heading", name="Cabin")).to_be_visible()

    # Each room lists the other one.
    open_switcher(page)
    expect(room_buttons(page)).to_have_text(["Home"])
    page.get_by_role("group", name="Rooms").get_by_role("button", name="Home").click()
    expect(page.get_by_role("heading", name="Home")).to_be_visible()
    open_switcher(page)
    expect(room_buttons(page)).to_have_text(["Cabin"])
    page.keyboard.press("Escape")

    # A normal visit to / still jumps to the last room. Switching rooms does
    # not count as signing in, so that is Cabin, the room that was signed in to last.
    page.goto(app_url(server))
    expect(page).to_have_url(re.compile(rf"/room/{cabin_slug}$"))
    expect(page.get_by_role("heading", name="Cabin")).to_be_visible()


def test_room_menu_has_no_rooms_and_the_switcher_shows_the_current_room(
    svelte_server, open_session
):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)  # Only Home is entered.

    # The ⋮ menu keeps its own entries and has no Rooms list.
    page.get_by_role("button", name="Room menu").click()
    expect(page.get_by_role("button", name="Share Room")).to_be_visible()
    expect(page.get_by_role("group", name="Rooms")).to_have_count(0)
    expect(page.get_by_role("button", name="Add room")).to_have_count(0)
    page.keyboard.press("Escape")

    # The room name opens the panel: the current room has a check and closes it.
    expect(page.get_by_role("heading", name="Home")).to_be_visible()
    open_switcher(page)
    current = page.get_by_role("group", name="Rooms").get_by_role("button", name="Home")
    expect(current).to_contain_text("✓")
    expect(current).to_have_attribute("aria-current", "true")
    current.click()
    expect(page.get_by_role("group", name="Rooms")).to_be_hidden()
    expect(page).to_have_url(re.compile(rf"/room/{server.room_slug}$"))

    # The small "admin" link at the foot of the panel opens the admin page.
    open_switcher(page)
    page.get_by_role("button", name="admin", exact=True).click()
    expect(page).to_have_url(re.compile(r"/admin$"))
