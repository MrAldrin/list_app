"""Svelte due center: the bell, list counts, date labels and reveal navigation.

The due views replace the old list-open and periodic toasts. Nothing here
expects a due warning toast; the bell and the counts carry the due information.
"""

import re
from datetime import date, timedelta

from playwright.sync_api import expect
from svelte_app import PHONE, add_item, create_list, share_link, sign_in
from test_svelte_items import saved_op

BELL = re.compile(r"^Due items:")


def _days(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def _set_date(page, name: str, day: str) -> None:
    page.get_by_role("button", name=re.compile(f"^{name}")).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Date").fill(day)
    with page.expect_response(saved_op):
        dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_be_hidden()


def test_bell_counts_overdue_and_today_and_groups_the_panel(
    svelte_server, open_session
):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_item(page, "eggs")
    add_item(page, "bread")
    _set_date(page, "milk", _days(-2))
    _set_date(page, "eggs", _days(0))
    _set_date(page, "bread", _days(10))

    # Overdue and today count; the item due in 10 days does not.
    bell = page.get_by_role("button", name=BELL)
    expect(bell).to_have_accessible_name("Due items: 2 due, 1 overdue")
    expect(bell.locator(".badge")).to_have_text("2")

    # The panel groups by day; empty groups do not show. Opening it keeps the count.
    bell.click()
    panel = page.get_by_role("dialog")
    expect(panel.get_by_role("heading", name=re.compile("^Overdue"))).to_be_visible()
    expect(panel.get_by_role("heading", name=re.compile("^Today"))).to_be_visible()
    expect(panel.get_by_role("heading", name=re.compile("^Tomorrow"))).to_have_count(0)
    expect(panel.get_by_role("heading", name=re.compile("^Next 7 days"))).to_have_count(
        0
    )
    expect(panel.get_by_role("heading", name=re.compile("^Later"))).to_be_visible()
    page.keyboard.press("Escape")
    expect(bell.locator(".badge")).to_have_text("2")


def test_room_card_counts_what_is_due_in_the_list(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    _set_date(page, "milk", _days(1))
    room_url = page.url.split("/list/")[0]
    page.goto(room_url)
    # The count sits beside the list link, in the same row.
    row = page.locator("li.list-row", has=page.get_by_role("link", name="Groceries"))
    expect(row).to_contain_text("1 due")
    expect(row).not_to_contain_text("overdue")


def test_reload_shows_no_due_toast(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    _set_date(page, "milk", _days(0))
    page.reload()
    expect(page.get_by_role("button", name=BELL)).to_be_visible()
    expect(page.locator(".toasts .toast", has_text="due")).to_have_count(0)


def test_reveal_clears_the_search_and_focuses_the_item(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_item(page, "eggs")
    _set_date(page, "eggs", _days(0))
    # A search hides eggs; the reveal from the bell clears it.
    field = page.get_by_label("Add or Search")
    field.fill("milk")
    page.get_by_role("button", name=BELL).click()
    page.get_by_role("dialog").get_by_role("link", name=re.compile("^eggs")).click()
    expect(field).to_have_value("")
    expect(page.get_by_role("button", name=re.compile("^eggs"))).to_be_focused()


def test_reveal_of_a_missing_item_says_so(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    list_url = create_list(page, "Groceries")
    add_item(page, "milk")
    # The link points at an item that is not on this list (deleted, or moved).
    page.goto(f"{list_url}?item=no-such-item&at=1")
    expect(page.get_by_text("no longer on this list")).to_be_visible()


def test_share_link_bell_shows_only_its_list(svelte_server, open_session):
    server = svelte_server
    owner = open_session("owner", **PHONE)
    sign_in(owner, server)
    create_list(owner, "Groceries")
    add_item(owner, "milk")
    _set_date(owner, "milk", _days(0))
    link = share_link(owner)
    # A second list in the same room, with its own due item the share must not show.
    owner.goto(
        link.split("/share/")[0] + "/room/" + owner.url.split("/room/")[1].split("/")[0]
    )
    create_list(owner, "Chores")
    add_item(owner, "dishes")
    _set_date(owner, "dishes", _days(0))

    # A browser with no room access opens the share link.
    guest = open_session("guest", **PHONE)
    guest.goto(link)
    expect(guest.get_by_role("heading", name="Groceries")).to_be_visible()
    bell = guest.get_by_role("button", name=BELL)
    expect(bell).to_have_accessible_name("Due items: 1 due, 0 overdue")
    bell.click()
    panel = guest.get_by_role("dialog")
    expect(panel.get_by_role("link", name=re.compile("^milk"))).to_be_visible()
    expect(panel.get_by_role("link", name=re.compile("^dishes"))).to_have_count(0)
    expect(panel.get_by_role("button", name="Whole room")).to_have_count(0)
