"""Svelte due center: the bell, list counts, date labels and reveal navigation.

The due views replace the old list-open and periodic toasts. Nothing here
expects a due warning toast; the bell and the counts carry the due information.
"""

import re
from datetime import date, datetime, timedelta

from playwright.sync_api import expect
from svelte_app import (
    PHONE,
    add_item,
    app_url,
    create_list,
    item_names,
    room_app_url,
    share_link,
    sign_in,
)
from test_svelte_items import saved_op
from test_svelte_offline_reconnect import member_with_list, view_offline
from test_svelte_room_switcher import CABIN_PASSWORD, create_room_as_admin
from test_svelte_share import reset_link, without_share_sheet

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
    expect(page.get_by_text("Showing the item. Cleared the search.")).to_be_visible()


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


def test_list_bell_switches_between_this_list_and_the_whole_room(
    svelte_server, open_session
):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    _set_date(page, "milk", _days(0))
    page.goto(room_app_url(server))
    create_list(page, "Chores")
    add_item(page, "dishes")
    _set_date(page, "dishes", _days(-1))
    page.goto(room_app_url(server))
    page.get_by_role("link", name="Groceries").click()
    expect(page.get_by_role("heading", name="Groceries")).to_be_visible()

    # On a list the bell starts on that list: only milk counts.
    bell = page.get_by_role("button", name=BELL)
    expect(bell).to_have_accessible_name("Due items: 1 due, 0 overdue")
    bell.click()
    panel = page.get_by_role("dialog")
    expect(panel.get_by_role("button", name="This list")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(panel.get_by_role("link", name=re.compile("^dishes"))).to_have_count(0)
    expect(panel.locator(".where")).to_have_count(0)

    # The whole room shows every due item, each with its list name.
    panel.get_by_role("button", name="Whole room").click()
    expect(panel.get_by_role("button", name="Whole room")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(panel.get_by_role("link", name=re.compile("^dishes"))).to_be_visible()
    expect(panel.locator("a", has_text="milk").locator(".where")).to_have_text(
        "Groceries"
    )
    expect(panel.locator("a", has_text="dishes").locator(".where")).to_have_text(
        "Chores"
    )

    panel.get_by_role("button", name="This list").click()
    expect(panel.get_by_role("link", name=re.compile("^dishes"))).to_have_count(0)


def test_whole_room_bell_ignores_another_room(svelte_server, open_session):
    server = svelte_server
    admin = open_session("admin", **PHONE)
    cabin_slug = create_room_as_admin(admin, server, "Cabin", CABIN_PASSWORD)
    cabin = open_session("cabin", **PHONE)
    cabin.goto(app_url(server, f"room/{cabin_slug}"))
    cabin.get_by_label("Room Password").fill(CABIN_PASSWORD)
    cabin.get_by_label("Room Password").press("Enter")
    expect(cabin.get_by_role("button", name="Add New List")).to_be_visible()
    create_list(cabin, "Chores")
    add_item(cabin, "cabin-item")
    _set_date(cabin, "cabin-item", _days(0))

    owner = open_session("owner", **PHONE)
    sign_in(owner, server)
    create_list(owner, "Groceries")
    add_item(owner, "milk")
    _set_date(owner, "milk", _days(0))
    owner.goto(room_app_url(server))
    bell = owner.get_by_role("button", name=BELL)
    expect(bell).to_have_accessible_name("Due items: 1 due, 0 overdue")
    bell.click()
    panel = owner.get_by_role("dialog")
    expect(panel.get_by_role("link", name=re.compile("^milk"))).to_be_visible()
    expect(panel.get_by_role("link", name=re.compile("^cabin-item"))).to_have_count(0)


def test_saved_panel_says_saved_and_offline_date_edits_count(
    svelte_server, open_session
):
    server = svelte_server
    page, url = member_with_list(
        open_session, server, "device", items=("milk", "bread")
    )
    _set_date(page, "milk", _days(0))
    view_offline(page, url)

    bell = page.get_by_role("button", name=BELL)
    expect(bell).to_have_accessible_name("Due items: 1 due, 0 overdue")
    bell.click()
    expect(page.get_by_role("dialog").get_by_role("note")).to_have_text(
        "Saved data. It may not be up to date."
    )
    page.keyboard.press("Escape")

    # A date set while offline is saved on this device and counts at once.
    page.get_by_role("button", name=re.compile("^bread")).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Date").fill(_days(0))
    dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_be_hidden()
    expect(bell).to_have_accessible_name("Due items: 2 due, 0 overdue")


def test_live_changes_update_the_open_panel_without_moving_focus(
    svelte_server, open_session
):
    server = svelte_server
    viewer = open_session("viewer", **PHONE)
    sign_in(viewer, server)
    create_list(viewer, "Groceries")
    add_item(viewer, "milk")
    other = open_session("other", **PHONE)
    sign_in(other, server)
    other.get_by_role("link", name="Groceries").click()
    expect(item_names(other)).to_have_text(["milk"])

    viewer.get_by_role("button", name=BELL).click()
    panel = viewer.get_by_role("dialog")
    expect(panel.get_by_text("No dated items.")).to_be_visible()
    viewer.evaluate("document.activeElement.dataset.keep = '1'")

    # Another device dates milk for today: the panel and the count change.
    _set_date(other, "milk", _days(0))
    expect(panel.get_by_role("heading", name=re.compile("^Today"))).to_be_visible()
    expect(viewer.get_by_role("button", name=BELL)).to_have_accessible_name(
        "Due items: 1 due, 0 overdue"
    )
    assert viewer.evaluate("document.activeElement.dataset.keep") == "1"


def test_bell_opens_and_closes_from_the_keyboard(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_item(page, "eggs")
    _set_date(page, "eggs", _days(0))
    bell = page.get_by_role("button", name=BELL)
    bell.focus()
    page.keyboard.press("Enter")
    panel = page.get_by_role("dialog")
    expect(panel.get_by_role("heading", name=re.compile("^Today"))).to_be_visible()

    # Escape closes the panel and gives the focus back to the bell.
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
    expect(bell).to_be_focused()

    # From the keyboard, a row reveals its item and focuses it.
    bell.press("Enter")
    page.get_by_role("dialog").get_by_role("link", name=re.compile("^eggs")).focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("button", name=re.compile("^eggs"))).to_be_focused()


def test_due_views_move_to_the_new_day_when_the_page_is_shown_again(
    svelte_server, open_session
):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    _set_date(page, "milk", _days(1))
    today = date.today()
    page.clock.set_fixed_time(datetime(today.year, today.month, today.day, 23, 59))
    page.reload()

    # Tomorrow's item is due tomorrow, so the bell counts it.
    bell = page.get_by_role("button", name=BELL)
    expect(bell).to_have_accessible_name("Due items: 1 due, 0 overdue")

    # The day turns over while the page is hidden; showing it again updates the views.
    tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())
    page.clock.set_fixed_time(tomorrow.replace(minute=0, second=30))
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    bell.click()
    expect(
        page.get_by_role("dialog").get_by_role("heading", name=re.compile("^Today"))
    ).to_be_visible()
    page.keyboard.press("Escape")


def test_deleting_the_last_due_list_clears_the_room_bell(svelte_server, open_session):
    server = svelte_server
    viewer = open_session("viewer", **PHONE)
    sign_in(viewer, server)
    create_list(viewer, "Groceries")
    add_item(viewer, "milk")
    _set_date(viewer, "milk", _days(0))
    viewer.goto(room_app_url(server))
    expect(viewer.get_by_role("button", name=BELL)).to_have_accessible_name(
        "Due items: 1 due, 0 overdue"
    )

    deleter = open_session("deleter", **PHONE)
    sign_in(deleter, server)
    deleter.get_by_role("button", name="Delete Groceries").click()
    deleter.get_by_role("dialog").get_by_role("button", name="Delete").click()
    expect(viewer.get_by_role("button", name=BELL)).to_have_accessible_name(
        "Due items: none due"
    )


def test_reset_share_link_sends_the_old_link_to_unavailable(
    svelte_server, open_session
):
    server = svelte_server
    owner = without_share_sheet(open_session("owner", **PHONE))
    sign_in(owner, server)
    create_list(owner, "Groceries")
    add_item(owner, "milk")
    _set_date(owner, "milk", _days(0))
    link = share_link(owner)

    guest = open_session("guest", **PHONE)
    guest.goto(link)
    expect(guest.get_by_role("button", name=BELL)).to_have_accessible_name(
        "Due items: 1 due, 0 overdue"
    )

    reset_link(owner)
    guest.goto(link)
    expect(
        guest.get_by_text("This list was deleted or you no longer have access.")
    ).to_be_visible()
    expect(guest.get_by_role("button", name=BELL)).to_have_count(0)


def test_timed_due_requires_zone_and_shows_server_confirmation(
    svelte_server, open_session
):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    page.get_by_role("button", name=re.compile("^milk")).click()
    dialog = page.get_by_role("dialog", name="Edit Item")
    dialog.get_by_label("Date").fill("2026-10-18")
    dialog.get_by_label("Due time (optional)").fill("09:00")
    expect(dialog.get_by_role("button", name="Save")).to_be_disabled()
    dialog.get_by_label(re.compile("Time zone")).fill("Europe/Oslo")
    expect(dialog.get_by_text(re.compile("Waiting to sync"))).to_be_visible()
    with page.expect_response(saved_op):
        dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_be_hidden()
    page.get_by_role("button", name=re.compile("^milk")).click()
    expect(dialog.get_by_text(re.compile("Server-confirmed UTC"))).to_be_visible()
    expect(dialog.get_by_label(re.compile("Time zone"))).to_have_value("Europe/Oslo")
