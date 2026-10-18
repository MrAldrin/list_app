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
