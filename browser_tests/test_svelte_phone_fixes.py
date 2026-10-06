"""Fixes from the owner's phone test (decision 149): "Log out" in the room
menu, "Back to admin" that follows the admin sign-in, and the list top bar.
"""

import re
from itertools import pairwise

from playwright.sync_api import expect
from svelte_app import (
    PHONE,
    admin_sign_in,
    app_url,
    create_list,
    room_app_url,
    sign_in,
)

SMALL_PHONE = {"viewport": {"width": 375, "height": 700}, "has_touch": True}
LONG_NAME = "A very long list name that cannot fit between the arrow and the menus " * 2


def test_log_out_is_the_last_entry_of_the_room_menu(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)

    # No Log out button in the header any more.
    expect(page.get_by_role("button", name="Log out")).to_have_count(0)
    page.get_by_role("button", name="Room menu").click()
    entries = page.locator(".menu").first.get_by_role("button")
    expect(entries.last).to_have_text("Log out")
    entries.last.click()
    expect(page.get_by_label("Room Password")).to_be_visible()


def test_back_to_admin_follows_the_admin_sign_in(svelte_server, open_session):
    server = svelte_server
    owner = open_session("admin", **PHONE)
    other = open_session("other", **PHONE)

    # A room member who is not admin never sees the link.
    sign_in(other, server)
    expect(other.get_by_role("link", name="Back to admin")).to_have_count(0)

    owner.goto(app_url(server, "admin"))
    admin_sign_in(owner, server)

    # Without ?admin=true, the room page still leads back to admin.
    sign_in(owner, server)
    expect(owner).to_have_url(room_app_url(server))
    back = owner.get_by_role("link", name="Back to admin")
    expect(back).to_be_visible()

    # It survives opening a list and going back (the back link has no query).
    create_list(owner, "Groceries")
    owner.get_by_role("link", name="Back to room").click()
    expect(owner).to_have_url(room_app_url(server))
    expect(back).to_be_visible()

    # It survives a reload, and it leads to the admin page.
    owner.reload()
    expect(back).to_be_visible()
    back.click()
    expect(owner).to_have_url(re.compile(r"/admin$"))

    # After the admin logs out, the link is gone (the room cookie stays).
    owner.get_by_role("button", name="Log out").click()
    expect(owner.get_by_label("Admin Password")).to_be_visible()
    owner.goto(room_app_url(server))
    expect(owner.get_by_role("button", name="Add New List")).to_be_visible()
    expect(owner.get_by_role("link", name="Back to admin")).to_have_count(0)


def test_list_top_bar_holds_the_name_between_arrow_and_menus(
    svelte_server, open_session
):
    page = open_session("small", **SMALL_PHONE)
    sign_in(page, svelte_server)
    create_list(page, LONG_NAME)

    bar = page.locator("header.bar")
    heading = bar.get_by_role("heading", level=1)
    back = bar.get_by_role("link", name="Back to room")
    options = bar.get_by_role("button", name="Options")
    menu = bar.get_by_role("button", name="List menu")

    # In the bar, in order: arrow, name, Options, menu; the name is cut off
    # with "…" and nothing leaves the screen.
    boxes = [e.bounding_box() for e in (back, heading, options, menu)]
    assert all(boxes)
    for left, right in pairwise(boxes):
        assert left["x"] + left["width"] <= right["x"] + 1, boxes
    assert boxes[-1]["x"] + boxes[-1]["width"] <= SMALL_PHONE["viewport"]["width"]
    assert heading.evaluate("h => h.scrollWidth > h.clientWidth")
    assert heading.evaluate("h => getComputedStyle(h).textOverflow") == "ellipsis"
    assert page.evaluate("document.documentElement.scrollWidth") <= 375
    # The full name stays available as the heading's name.
    expect(heading).to_have_text(LONG_NAME)

    # Options (outside the menu) still toggles; the menu has dark mode, no
    # button for it sits in the bar.
    options.click()
    expect(bar.get_by_role("button", name="Done")).to_be_visible()
    bar.get_by_role("button", name="Done").click()
    expect(bar.get_by_role("button", name="Dark mode")).to_have_count(0)
    menu.click()
    expect(page.get_by_role("button", name="Dark mode")).to_be_visible()
    expect(page.get_by_role("button", name="Share List")).to_be_visible()
    page.keyboard.press("Escape")

    # The bar stays on top while the page scrolls, with the name in it.
    for number in range(30):
        field = page.get_by_label("Add or Search")
        field.fill(f"item {number}")
        field.press("Enter")
    page.mouse.wheel(0, 2000)
    expect(heading).to_be_in_viewport()
    # The add field stays below the bar.
    expect(page.get_by_label("Add or Search")).to_be_attached()
