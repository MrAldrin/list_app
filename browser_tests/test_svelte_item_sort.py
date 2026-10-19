"""Svelte list page: the item sort, chosen in Options and saved in this browser.

The sort is personal like "Show quantities": it is kept after a reload. The
rules (open items first, ties, dates, no time) are covered by unit tests.
"""

from playwright.sync_api import expect
from svelte_app import PHONE, add_item, create_list, item_names, sign_in

NAME_Z_TO_A = "Name Z\N{EN DASH}A"


def open_options(page):
    page.get_by_role("button", name="Options").click()
    return page.get_by_label("Sort")


def test_sort_choice_is_kept_per_browser_after_reload(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    # Added in this order: milk is the oldest, zucchini the newest.
    add_item(page, "milk")
    add_item(page, "apple")
    add_item(page, "zucchini")

    # The default is name A to Z.
    expect(item_names(page)).to_have_text(["apple", "milk", "zucchini"])
    sort = open_options(page)
    expect(sort).to_have_value("name-asc")

    sort.select_option(label="Added: newest first")
    expect(item_names(page)).to_have_text(["zucchini", "apple", "milk"])

    # The choice is saved in this browser, so it survives a reload.
    page.reload()
    expect(item_names(page)).to_have_text(["zucchini", "apple", "milk"])
    sort = open_options(page)
    expect(sort).to_have_value("added-desc")

    sort.select_option(label=NAME_Z_TO_A)
    expect(item_names(page)).to_have_text(["zucchini", "milk", "apple"])


def test_checked_rows_wait_for_the_taps_to_settle(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    for name in ("apple", "milk", "zucchini"):
        add_item(page, name)
    expect(item_names(page)).to_have_text(["apple", "milk", "zucchini"])

    # A checked row stays where it is, so the next row does not move under the thumb.
    page.get_by_role("checkbox", name="apple").click()
    expect(page.get_by_role("checkbox", name="apple")).to_be_checked()
    # Kept: the rows must not move during the hold, which is HOLD_MS (1.5 s).
    # The window stays under that, so it checks the hold itself.
    page.wait_for_timeout(500)
    expect(item_names(page)).to_have_text(["apple", "milk", "zucchini"])

    # Another tap restarts the wait, so milk stays too.
    page.get_by_role("checkbox", name="milk").click()
    expect(page.get_by_role("checkbox", name="milk")).to_be_checked()
    page.wait_for_timeout(500)
    expect(item_names(page)).to_have_text(["apple", "milk", "zucchini"])

    # Once the taps settle, the checked rows move below the open one.
    expect(item_names(page)).to_have_text(["zucchini", "apple", "milk"])
