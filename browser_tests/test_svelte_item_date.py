"""Svelte list page: the optional date on an item."""

import re

from playwright.sync_api import expect
from svelte_app import PHONE, add_item, create_list, sign_in
from test_svelte_items import saved_op


def test_item_date_is_saved_shown_and_cleared(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    dates = page.locator("ul.items .date")
    # The row name includes its date once it has one, e.g. "milk 20 Oct".
    milk = page.get_by_role("button", name=re.compile("^milk"))
    dialog = page.get_by_role("dialog")

    # Set a date: the row shows it as "20 Oct".
    milk.click()
    dialog.get_by_label("Date").fill("2026-10-20")
    with page.expect_response(saved_op):
        dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_be_hidden()
    expect(dates).to_have_text("20 Oct")

    # The date is saved on the server, so it is still there after a reload.
    page.reload()
    expect(dates).to_have_text("20 Oct")

    # The dialog holds the date; Clear removes it and Save shows no date.
    milk.click()
    expect(dialog.get_by_label("Date")).to_have_value("2026-10-20")
    dialog.get_by_role("button", name="Clear").click()
    with page.expect_response(saved_op):
        dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_be_hidden()
    expect(dates).to_have_count(0)
