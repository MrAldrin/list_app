"""Svelte: a stale room or share page cannot write after a list or room is deleted.

The Svelte versions of `test_deleted_lists.py`. The stale page's live stream
is held back, so it does not learn about the delete and really sends its
action. The test then checks the server's answer, the page and the database.
"""

import re

import pytest
from playwright.sync_api import Page, expect
from svelte_app import PHONE, add_item, create_list, room_app_url, sign_in
from test_svelte_share import RESET_MESSAGE, share_link, without_share_sheet

OPS = re.compile(r"/api/v1/(rooms|share)/[^/]+/ops$")


def hold_live_updates(page: Page) -> None:
    """The page's live stream never connects, so it misses the delete."""
    page.route(re.compile(r"/api/v1/(rooms|share)/[^/]+/events"), lambda route: None)


def prepare_action(page: Page, action: str):
    """Get the action ready; return the step that sends it."""
    if action == "add":
        page.get_by_label("Add or Search").fill("forbidden")
        return lambda: page.get_by_label("Add or Search").press("Enter")
    if action == "edit":
        page.get_by_role("button", name="milk", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Item Name").fill("forbidden")
        return dialog.get_by_role("button", name="Save").click
    if action == "toggle":
        return page.get_by_role("checkbox", name="milk").click
    if action == "quantity":
        page.get_by_role("button", name="Options").click()
        page.get_by_role("switch", name="Show quantities").check()
        return page.get_by_role("button", name="More milk").click
    if action == "tag":
        page.get_by_role("button", name="Options").click()
        page.get_by_label("Add Tag").fill("forbidden")
        return lambda: page.get_by_label("Add Tag").press("Enter")
    if action == "undo":
        page.get_by_role("button", name="Options").click()
        page.get_by_role("button", name="Delete milk").click()
        expect(page.get_by_role("button", name="Undo")).to_be_visible()
        return page.get_by_role("button", name="Undo").click
    raise AssertionError(action)


def open_stale_page(member: Page, open_session, server, role: str) -> Page:
    """The room's list page (signed in) or the list's share page."""
    if role == "room":
        stale = open_session("stale", **PHONE)
        sign_in(stale, server)
        hold_live_updates(stale)
        stale.get_by_role("link", name="Groceries").click()
    else:
        link = share_link(member)
        stale = open_session("stale", **PHONE)
        hold_live_updates(stale)
        stale.goto(link)
    expect(stale.get_by_role("checkbox", name="milk")).to_be_visible()
    return stale


def setup(open_session, server) -> Page:
    member = without_share_sheet(open_session("member", **PHONE))
    sign_in(member, server)
    create_list(member, "Groceries")
    add_item(member, "milk")
    return member


def send_stale_action(stale: Page, fire, role: str) -> None:
    """Send the action; it must reach the server and be refused."""
    with stale.expect_response(OPS) as answer:
        fire()
    if role == "room":
        assert answer.value.status == 200
        assert answer.value.json()["status"] == "rejected", answer.value.json()
    else:
        assert answer.value.status == 401


# Each action runs in every engine, with the room and share pages alternated
# per engine (as in `test_deleted_lists.py`). WebKit takes Chromium's role.
@pytest.mark.parametrize(
    "action, chromium_role",
    [
        ("add", "room"),
        ("edit", "public"),
        ("toggle", "room"),
        ("quantity", "public"),
        ("tag", "room"),
        ("undo", "public"),
    ],
    ids=["add", "edit", "toggle", "quantity", "tag", "undo"],
)
def test_stale_page_cannot_write_after_list_deletion(
    svelte_server, open_session, browser, action, chromium_role
):
    server = svelte_server
    other_role = "public" if chromium_role == "room" else "room"
    role = {"chromium": chromium_role, "firefox": other_role, "webkit": chromium_role}[
        browser.browser_type.name
    ]
    member = setup(open_session, server)
    stale = open_stale_page(member, open_session, server, role)

    # The delete waits in its confirm dialog, so the action follows it quickly
    # (an Undo lasts only 5 s).
    member.goto(room_app_url(server))
    member.get_by_role("button", name="Delete Groceries").click()
    fire = prepare_action(stale, action)
    member.get_by_role("dialog").get_by_role("button", name="Delete").click()
    expect(member.get_by_text("Deleted 'Groceries'")).to_be_visible()
    assert not server.query("SELECT id FROM lists WHERE name = 'Groceries'")

    send_stale_action(stale, fire, role)
    expect(stale.get_by_label("Add or Search")).to_have_count(0)
    if role == "room":
        expect(stale.get_by_text("This list was deleted.")).to_be_visible()
        stale.get_by_role("link", name="Back to room").click()
        expect(stale).to_have_url(room_app_url(server))
    else:
        expect(stale.get_by_text(RESET_MESSAGE)).to_be_visible()
        expect(stale.get_by_role("link", name="Back to room")).to_have_count(0)
    assert not server.query("SELECT id FROM items WHERE name = 'forbidden'")
    assert server.query("SELECT COUNT(*) FROM items") == [(0,)]
    assert not server.query("SELECT id FROM lists WHERE name = 'Groceries'")


@pytest.mark.parametrize("role", ["room", "public"])
def test_stale_page_after_room_deletion_has_no_room_navigation(
    svelte_server, open_session, role
):
    server = svelte_server
    member = setup(open_session, server)
    stale = open_stale_page(member, open_session, server, role)
    fire = prepare_action(stale, "add")

    member.goto(room_app_url(server))
    member.get_by_role("button", name="Room menu").click()
    member.get_by_role("button", name="Delete Room").click()
    member.get_by_label("Enter Room Password to Confirm").fill(server.password)
    member.get_by_role("dialog").get_by_role("button", name="Delete").click()
    expect(member.get_by_text("Room deleted")).to_be_visible()
    assert not server.query("SELECT id FROM rooms WHERE name = 'Home'")

    with stale.expect_response(OPS) as answer:
        fire()
    assert answer.value.status == 401
    expect(stale.get_by_label("Add or Search")).to_have_count(0)
    expect(stale.get_by_role("link", name="Back to room")).to_have_count(0)
    if role == "room":
        expect(stale.get_by_label("Room Password")).to_be_visible()
    else:
        expect(stale.get_by_text(RESET_MESSAGE)).to_be_visible()
    assert not server.query("SELECT id FROM items WHERE name = 'forbidden'")
