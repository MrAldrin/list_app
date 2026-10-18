"""Svelte list page: how often an item was added, shown in the item dialog."""

import re

from playwright.sync_api import expect
from svelte_app import PHONE, add_item, create_list, sign_in
from test_svelte_items import saved_op


def test_item_dialog_counts_adds_and_unchecks(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    milk = page.get_by_role("button", name=re.compile("^milk"))
    dialog = page.get_by_role("dialog")

    # A new item was added once. The line is not on the list row.
    milk.click()
    expect(dialog.get_by_text("Added once")).to_be_visible()
    dialog.get_by_role("button", name="Cancel").click()
    expect(dialog).to_be_hidden()
    expect(page.locator("ul.items")).not_to_contain_text("Added once")

    # Checking is not an add: the count stays.
    with page.expect_response(saved_op):
        page.get_by_role("checkbox", name="milk").check()
    milk.click()
    expect(dialog.get_by_text("Added once")).to_be_visible()
    dialog.get_by_role("button", name="Cancel").click()

    # Unchecking is an add: the dialog now says twice.
    with page.expect_response(saved_op):
        page.get_by_role("checkbox", name="milk").uncheck()
    milk.click()
    expect(dialog.get_by_text("Added 2 times")).to_be_visible()
