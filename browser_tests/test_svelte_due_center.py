"""Svelte due center: the bell, list counts, date labels and reveal navigation.

The due views replace the old list-open and periodic toasts. Nothing here
expects a due warning toast; the bell and the counts carry the due information.
"""

import re
from datetime import UTC, date, datetime, timedelta

import pytest
from playwright.sync_api import expect
from svelte_app import (
    PHONE,
    add_item,
    api_seed,
    api_sign_in,
    app_url,
    create_list,
    dismiss_toasts,
    item_names,
    member_with_list,
    open_list,
    room_app_url,
    share_link,
    sign_in,
    view_offline,
)
from test_svelte_items import saved_op
from test_svelte_room_switcher import CABIN_PASSWORD, create_room_as_admin
from test_svelte_share import reset_link, without_share_sheet

BELL = re.compile(r"^Due items:")


def _seeded(page, server, lists, open_name: str | None = "Groceries") -> dict[str, str]:
    """Sign in and build the lists through the API; open one list page."""
    api_sign_in(page, server)
    urls = api_seed(page, server, lists)
    if open_name:
        open_list(page, urls[open_name], open_name)
    return urls


def _days(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def _set_date(page, name: str, day: str) -> None:
    dismiss_toasts(page)
    page.get_by_role("button", name=re.compile(f"^{name}")).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Date").fill(day)
    with page.expect_response(saved_op):
        dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_be_hidden()


@pytest.mark.all_engines
@pytest.mark.tier_core
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


def test_bell_uses_browser_day_before_reminder_setup(
    svelte_server, open_session
) -> None:
    page = open_session("phone", timezone_id="America/Los_Angeles", **PHONE)
    # July 21 in Los Angeles, July 22 in Oslo. Today is not Oslo's date.
    page.clock.set_fixed_time(datetime(2090, 7, 22, 2, tzinfo=UTC))
    _seeded(page, svelte_server, {"Groceries": ["milk"]})
    _set_date(page, "milk", "2090-07-21")

    bell = page.get_by_role("button", name=BELL)
    expect(bell).to_have_accessible_name("Due items: 1 due, 0 overdue")
    bell.click()
    expect(
        page.get_by_role("dialog").get_by_role("heading", name=re.compile("^Today"))
    ).to_be_visible()


def test_reveal_clears_the_search_and_focuses_the_item(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    _seeded(page, server, {"Groceries": ["milk", {"name": "eggs", "date": _days(0)}]})
    # A search hides eggs; the reveal from the bell clears it.
    field = page.get_by_label("Add or Search")
    field.fill("milk")
    page.get_by_role("button", name=BELL).click()
    page.get_by_role("dialog").get_by_role("link", name=re.compile("^eggs")).click()
    expect(field).to_have_value("")
    expect(page.get_by_role("button", name=re.compile("^eggs"))).to_be_focused()
    expect(page.get_by_text("Showing the item. Cleared the search.")).to_be_visible()


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
    _seeded(
        owner,
        server,
        {"Groceries": [{"name": "milk", "date": _days(0)}]},
        open_name=None,
    )
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
    urls = _seeded(viewer, server, {"Groceries": ["milk"]})
    other = open_session("other", **PHONE)
    api_sign_in(other, server)
    open_list(other, urls["Groceries"], "Groceries")
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

    # The room bell also updates when another device deletes the last dated list.
    viewer.goto(room_app_url(server))
    bell = viewer.get_by_role("button", name=BELL)
    expect(bell).to_have_accessible_name("Due items: 1 due, 0 overdue")
    other.goto(room_app_url(server))
    other.get_by_role("button", name="Delete Groceries").click()
    other.get_by_role("dialog").get_by_role("button", name="Delete").click()
    expect(bell).to_have_accessible_name("Due items: none due")


@pytest.mark.all_engines
@pytest.mark.tier_core
def test_bell_opens_and_closes_from_the_keyboard(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    _seeded(page, server, {"Groceries": ["milk", {"name": "eggs", "date": _days(0)}]})
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


def test_reset_share_link_sends_the_old_link_to_unavailable(
    svelte_server, open_session
):
    server = svelte_server
    owner = without_share_sheet(open_session("owner", **PHONE))
    _seeded(owner, server, {"Groceries": [{"name": "milk", "date": _days(0)}]})
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


@pytest.mark.all_engines
@pytest.mark.tier_core
def test_timed_due_requires_zone_and_shows_server_confirmation(
    svelte_server, open_session
):
    page = open_session("phone", **PHONE)
    _seeded(page, svelte_server, {"Groceries": ["milk"]})
    page.get_by_role("button", name=re.compile("^milk")).click()
    dialog = page.get_by_role("dialog", name="Edit Item")
    dialog.get_by_label("Date").fill("2026-10-18")
    expect(dialog.get_by_label("Due time (optional)")).to_have_attribute(
        "inputmode", "text"
    )
    dialog.get_by_label("Due time (optional)").fill("09:00")
    expect(dialog.get_by_text("Time zone: Europe/Oslo", exact=True)).to_be_visible()
    expect(dialog.get_by_role("button", name="Save")).to_be_enabled()
    dialog.get_by_text("Change time zone", exact=True).click()
    dialog.get_by_label(re.compile("Time zone")).fill("Europe/Oslo")
    expect(dialog.get_by_text("The time will be confirmed when saved.")).to_be_visible()
    with page.expect_response(saved_op):
        dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_be_hidden()
    page.get_by_role("button", name=re.compile("^milk")).click()
    expect(dialog.get_by_text(re.compile(r"Saved time \(UTC\):"))).to_be_visible()
    expect(dialog.get_by_label("Due time (optional)")).to_have_value("09:00")
    expect(dialog.get_by_label(re.compile("Time zone"))).to_have_value("Europe/Oslo")


@pytest.mark.all_engines
def test_zone_validation_online_and_offline(svelte_server, open_session):
    page, url = member_with_list(open_session, svelte_server, "zone-validation")
    for offline in (False, True):
        if offline:
            view_offline(page, url)
        page.get_by_role("button", name="milk", exact=True).click()
        dialog = page.get_by_role("dialog", name="Edit Item")
        dialog.get_by_label("Date").fill("2026-10-18")
        dialog.get_by_label("Due time (optional)").fill("09:00")
        dialog.get_by_text("Change time zone", exact=True).click()
        zone = dialog.get_by_label(re.compile("Time zone"))
        for invalid in ("", "Not/AZone", "a" * 65):
            zone.fill(invalid)
            expect(dialog.get_by_role("button", name="Save")).to_be_disabled()
            expect(zone).to_have_attribute("aria-invalid", "true")
            expect(
                dialog.get_by_text(
                    "Enter a valid time zone, up to 64 characters, such as Europe/Oslo."
                )
            ).to_be_visible()
        for valid in ("UTC", "Asia/Kathmandu"):
            zone.fill(valid)
            expect(dialog.get_by_role("button", name="Save")).to_be_enabled()
        dialog.get_by_role("button", name="Cancel").click()
        expect(dialog).to_have_count(0)
