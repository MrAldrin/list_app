"""Svelte hide-done settings: every mode, shared live between viewers.

The Svelte version of `test_visibility_settings.py`. A room member and a
share-link visitor change the settings of one list; both see each change,
hidden items stay searchable, and the numbers are kept when the switch goes
off and on again. Day boundaries are covered by unit tests.
"""

import re

from playwright.sync_api import Page, expect
from svelte_app import PHONE, add_item, create_list, sign_in
from test_svelte_share import share_link, without_share_sheet

SAVED = re.compile(r"/api/v1/(rooms|share)/[^/]+/ops$")


def milk(page: Page):
    return page.get_by_role("checkbox", name="milk")


def mode(page: Page, name: str):
    return page.get_by_role("radio", name=name)


def settings(server):
    return server.query(
        "SELECT hide_done_mode, hide_done_age_days, hide_done_recent_count "
        "FROM lists WHERE name = 'Groceries'"
    )[0]


def choose(page: Page, name: str) -> None:
    """Tap a mode; the radio itself is hidden under its label."""
    with page.expect_response(SAVED):
        page.locator("fieldset label").filter(has_text=name).click()
    expect(mode(page, name)).to_be_checked()


def save_count(page: Page, label: str, value: str) -> None:
    field = page.get_by_label(label)
    field.fill(value)
    with page.expect_response(SAVED):
        field.press("Tab")


def test_hide_done_modes_history_and_shared_updates(svelte_server, open_session):
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    create_list(member, "Groceries")
    add_item(member, "milk")
    milk(member).check()
    expect(milk(member)).to_be_checked()

    visitor.goto(share_link(member))
    expect(milk(visitor)).to_be_checked()
    member.get_by_role("button", name="Options").click()
    switch = member.get_by_role("switch", name="Hide checked-off items")
    expect(switch).not_to_be_checked()
    assert settings(server) == ("off", 7, 10)

    # "All": the checked item goes for both viewers.
    with member.expect_response(SAVED):
        switch.check()
    expect(milk(member)).to_have_count(0)
    expect(milk(visitor)).to_have_count(0)
    assert settings(server)[0] == "all"

    # A hidden item is still found, and adding it brings it back unchecked.
    visitor.get_by_label("Add or Search").fill("milk")
    visitor.get_by_role("listbox", name="Suggestions").get_by_role(
        "option", name="milk"
    ).click()
    expect(visitor.get_by_text("Restored milk!")).to_be_visible()
    expect(milk(visitor)).not_to_be_checked()
    expect(milk(member)).not_to_be_checked()

    # "After X days": a fresh check stays visible; zero is rejected.
    visitor.get_by_role("button", name="Options").click()
    choose(visitor, "After X days")
    expect(visitor.get_by_label("Days before hiding")).to_have_value("7")
    expect(mode(member, "After X days")).to_be_checked()
    assert settings(server)[0] == "age"
    milk(visitor).check()
    expect(milk(visitor)).to_be_checked()
    expect(milk(member)).to_be_checked()
    field = visitor.get_by_label("Days before hiding")
    expect(field).to_have_attribute("min", "1")
    field.fill("0")
    field.press("Tab")
    expect(field).to_have_value("7")
    expect(
        visitor.get_by_text("Enter a whole number between 1 and 100000.")
    ).to_be_visible()
    assert settings(server) == ("age", 7, 10)
    expect(milk(visitor)).to_be_visible()
    expect(milk(member)).to_be_visible()
    save_count(visitor, "Days before hiding", "1")
    expect(milk(visitor)).to_be_visible()
    expect(milk(member)).to_be_visible()

    # "Keep last X": zero is rejected; one keeps the newest checked item.
    choose(visitor, "Keep last X")
    expect(mode(member, "Keep last X")).to_be_checked()
    expect(mode(member, "After X days")).not_to_be_checked()
    expect(visitor.get_by_label("Checked items to keep")).to_have_value("10")
    field = visitor.get_by_label("Checked items to keep")
    expect(field).to_have_attribute("min", "1")
    field.fill("0")
    field.press("Tab")
    expect(field).to_have_value("10")
    assert settings(server) == ("recent", 1, 10)
    save_count(visitor, "Checked items to keep", "1")
    expect(milk(visitor)).to_be_visible()
    expect(milk(member)).to_be_visible()

    # Off shows everything; on again starts at "All" and keeps the numbers.
    visitor_switch = visitor.get_by_role("switch", name="Hide checked-off items")
    with visitor.expect_response(SAVED):
        visitor_switch.uncheck()
    expect(milk(visitor)).to_be_visible()
    expect(milk(member)).to_be_visible()
    with visitor.expect_response(SAVED):
        visitor_switch.check()
    expect(milk(visitor)).to_have_count(0)
    expect(mode(member, "All")).to_be_checked()
    assert settings(server) == ("all", 1, 1)
