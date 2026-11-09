"""Svelte list page: tags as one scrolling row, Options > Tags, and shared tag settings."""

import re

import pytest
from playwright.sync_api import expect
from svelte_app import (
    PHONE,
    add_item,
    add_list_tag,
    create_list,
    item_names,
    sign_in,
)


def chips(page):
    return page.get_by_role("list", name="Tags")


@pytest.mark.chromium_only
def test_new_tags_come_from_options_not_the_tag_row(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    add_item(page, "milk")

    # No tags yet: no tag row, and no "+" chip to add one.
    expect(chips(page)).to_have_count(0)
    expect(page.get_by_role("button", name="New tag")).to_have_count(0)

    add_list_tag(page, "Lidl")
    expect(chips(page).get_by_role("button")).to_have_count(1)
    expect(chips(page).get_by_role("button", name="Lidl", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Lidl tag for milk")).to_be_visible()


@pytest.mark.chromium_only
def test_tap_filters_the_items(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_item(page, "bread")
    add_list_tag(page, "Lidl")
    page.get_by_role("button", name="Lidl tag for milk").click()

    lidl = chips(page).get_by_role("button", name="Lidl", exact=True)
    page.get_by_role("button", name="Done").click()
    lidl.click()
    expect(lidl).to_have_attribute("aria-pressed", "true")
    expect(item_names(page)).to_have_text(["milk"])
    lidl.click()
    expect(item_names(page)).to_have_text(["bread", "milk"])


@pytest.mark.chromium_only
def test_options_click_opens_the_card_and_rename_keeps_the_filter(
    svelte_server, open_session
):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_list_tag(page, "Lidl")
    page.get_by_role("button", name="Lidl tag for milk").click()
    page.get_by_role("button", name="Done").click()
    chips(page).get_by_role("button", name="Lidl", exact=True).click()
    expect(item_names(page)).to_have_text(["milk"])

    # Options open: a tap on the chip opens its card instead of filtering.
    page.get_by_role("button", name="Options").click()
    chips(page).get_by_role("button", name="Lidl", exact=True).click()
    card = page.get_by_role("dialog", name="Edit Tag")
    card.get_by_label("Tag Name").fill("Aldi")
    card.get_by_role("button", name="Save").click()
    expect(page.get_by_role("dialog", name="Edit Tag")).to_have_count(0)

    # One rename on the server: the chip, the item letter and the filter follow.
    page.get_by_role("button", name="Done").click()
    expect(
        chips(page).get_by_role("button", name="Aldi", exact=True)
    ).to_have_attribute("aria-pressed", "true")
    expect(page.get_by_role("button", name="Aldi tag for milk")).to_be_visible()
    expect(item_names(page)).to_have_text(["milk"])


@pytest.mark.chromium_only
def test_recolor_and_delete_with_undo(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_list_tag(page, "Lidl")
    milk_lidl = page.get_by_role("button", name="Lidl tag for milk")

    chips(page).get_by_role("button", name="Lidl", exact=True).click()
    card = page.get_by_role("dialog", name="Edit Tag")
    card.get_by_role("button", name="Color 7").click()
    card.get_by_role("button", name="Save").click()
    expect(page.get_by_role("dialog", name="Edit Tag")).to_have_count(0)
    page.get_by_role("button", name="Done").click()
    # Color 7 is palette index 6, the last one.
    expect(milk_lidl).to_have_attribute("style", "--tag: var(--tag-6);")

    # Delete from the card, then undo.
    page.get_by_role("button", name="Options").click()
    chips(page).get_by_role("button", name="Lidl", exact=True).click()
    page.get_by_role("dialog", name="Edit Tag").get_by_role(
        "button", name="Delete tag"
    ).click()
    expect(page.get_by_text("Deleted tag Lidl")).to_be_visible()
    expect(page.get_by_role("button", name="Lidl tag for milk")).to_have_count(0)
    page.get_by_role("button", name="Undo").click()
    expect(page.get_by_text("Restored tag Lidl")).to_be_visible()
    expect(page.get_by_role("button", name="Lidl tag for milk")).to_be_visible()


@pytest.mark.chromium_only
def test_one_tag_mode_asks_first_and_keeps_the_first_tag(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_list_tag(page, "Lidl")
    add_list_tag(page, "Market")
    page.get_by_role("button", name="Lidl tag for milk").click()
    page.get_by_role("button", name="Market tag for milk").click()

    # The milk has two tags: the switch asks, and cancelling keeps both.
    page.get_by_role("button", name="Done").click()
    page.get_by_role("button", name="Options").click()
    page.get_by_role("button", name="Tags").click()
    tags_dialog = page.get_by_role("dialog", name="Tags")
    tags_dialog.get_by_role("button", name="One tag per item").click()
    confirm = page.get_by_role(
        "dialog", name=re.compile("has several tags|have several tags")
    )
    expect(confirm).to_be_visible()
    confirm.get_by_role("button", name="Cancel").click()
    expect(confirm).to_have_count(0)
    expect(
        tags_dialog.get_by_role("button", name="One tag per item")
    ).to_have_attribute("aria-pressed", "false")

    # Confirming keeps only the first tag of each item, in the list's order.
    tags_dialog.get_by_role("button", name="One tag per item").click()
    page.get_by_role(
        "dialog", name=re.compile("has several tags|have several tags")
    ).get_by_role("button", name="Keep first tags").click()
    expect(
        tags_dialog.get_by_role("button", name="One tag per item")
    ).to_have_attribute("aria-pressed", "true")
    tags_dialog.get_by_role("button", name="Close").click()
    expect(page.get_by_role("button", name="Lidl tag for milk")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.get_by_role("button", name="Market tag for milk")).to_have_attribute(
        "aria-pressed", "false"
    )


@pytest.mark.chromium_only
def test_tag_settings_are_the_same_in_a_second_browser(svelte_server, open_session):
    server = svelte_server
    phone = open_session("phone-a", **PHONE)
    sign_in(phone, server)
    list_url = create_list(phone, "Groceries")
    add_item(phone, "milk")
    add_list_tag(phone, "Lidl")
    phone.get_by_role("button", name="Tags").click()
    phone.get_by_role("dialog", name="Tags").get_by_role(
        "switch", name="Show tags on items"
    ).uncheck()
    phone.get_by_role("button", name="Close").click()

    other = open_session("phone-b", **PHONE)
    sign_in(other, server)
    other.goto(list_url)
    expect(other.get_by_role("button", name="Lidl tag for milk")).to_have_count(0)
    other.get_by_role("button", name="Options").click()
    other.get_by_role("button", name="Tags").click()
    expect(
        other.get_by_role("dialog", name="Tags").get_by_role(
            "switch", name="Show tags on items"
        )
    ).not_to_be_checked()


@pytest.mark.chromium_only
def test_edit_item_tag_chips_light_up_at_once(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_list_tag(page, "Lidl")
    add_list_tag(page, "Market")

    # Tags in Edit Item save at once, so the chip shows its new state at once.
    page.get_by_role("button", name="milk", exact=True).click()
    dialog = page.get_by_role("dialog", name="Edit Item")
    lidl = dialog.get_by_role("button", name="Lidl", exact=True)
    market = dialog.get_by_role("button", name="Market", exact=True)
    lidl.click()
    expect(lidl).to_have_attribute("aria-pressed", "true")
    market.click()
    expect(market).to_have_attribute("aria-pressed", "true")
    lidl.click()
    expect(lidl).to_have_attribute("aria-pressed", "false")
    dialog.get_by_role("button", name="Cancel").click()
    expect(page.get_by_role("button", name="Market tag for milk")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.get_by_role("button", name="Lidl tag for milk")).to_have_attribute(
        "aria-pressed", "false"
    )
