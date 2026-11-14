"""Svelte list page: the item sort, chosen in Options and saved in this browser.

The sort is personal like "Show quantities": it is kept after a reload. The
rules (open items first, ties, dates, no time) are covered by unit tests.
"""

from playwright.sync_api import expect
from svelte_app import (
    PHONE,
    add_item,
    api_seed,
    api_sign_in,
    item_names,
    open_list,
)

NAME_Z_TO_A = "Z\N{EN DASH}A"


def open_options(page):
    """Opens Options; returns the sort select and direction button."""
    page.get_by_role("button", name="Options").click()
    return page.get_by_label("Sort"), page.get_by_role("button", name="Order:")


def test_sort_choice_is_kept_per_browser_after_reload(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    api_sign_in(page, server)
    open_list(page, api_seed(page, server, {"Groceries": []})["Groceries"], "Groceries")
    # Added in this order: milk is the oldest, zucchini the newest.
    add_item(page, "milk")
    add_item(page, "apple")
    add_item(page, "zucchini")

    # The default is name A to Z.
    expect(item_names(page)).to_have_text(["apple", "milk", "zucchini"])
    sort_by, order = open_options(page)
    expect(sort_by).to_have_value("name")
    expect(order).to_have_attribute("aria-label", "Order: A\N{EN DASH}Z. Reverse")

    # A new "Sort by" starts in its default order: newest first.
    sort_by.select_option(label="Added")
    expect(order).to_have_attribute("aria-label", "Order: Newest first. Reverse")
    expect(item_names(page)).to_have_text(["zucchini", "apple", "milk"])

    # The choice is saved in this browser, so it survives a reload.
    page.reload()
    expect(item_names(page)).to_have_text(["zucchini", "apple", "milk"])
    sort_by, order = open_options(page)
    expect(sort_by).to_have_value("added")
    expect(order).to_have_attribute("aria-label", "Order: Newest first. Reverse")

    # Back to name, then the other direction.
    sort_by.select_option(label="Name")
    expect(item_names(page)).to_have_text(["apple", "milk", "zucchini"])
    order.click()
    expect(order).to_have_attribute("aria-label", f"Order: {NAME_Z_TO_A}. Reverse")
    expect(item_names(page)).to_have_text(["zucchini", "milk", "apple"])
