"""Svelte list page: items, quantities, edits, undo, tags and hide-done."""

import json
import re

from playwright.sync_api import expect
from svelte_app import PHONE, add_item, create_list, item_names, sign_in


def test_add_restore_check_quantity_edit_and_undo(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    field = page.get_by_label("Add or Search")

    # Add: names are trimmed and lowercased; the field clears and keeps focus.
    field.fill("  Milk ")
    field.press("Enter")
    expect(page.get_by_text("Added milk")).to_be_visible()
    expect(field).to_have_value("")
    expect(field).to_be_focused()
    add_item(page, "bread")
    add_item(page, "apples")
    expect(item_names(page)).to_have_text(["apples", "bread", "milk"])

    # A duplicate is not added twice.
    field.fill("MILK")
    field.press("Enter")
    expect(page.get_by_text("'milk' is already on the list")).to_be_visible()
    expect(item_names(page)).to_have_count(3)

    # Check off: the item moves below the open items; uncheck moves it back.
    with page.expect_response(saved_op):
        page.get_by_role("checkbox", name="apples").check()
    expect(item_names(page)).to_have_text(["bread", "milk", "apples"])
    page.get_by_role("checkbox", name="apples").uncheck()
    expect(item_names(page)).to_have_text(["apples", "bread", "milk"])

    # Adding a checked-off item restores it (here through a suggestion).
    with page.expect_response(saved_op):
        page.get_by_role("checkbox", name="apples").check()
    expect(page.get_by_role("checkbox", name="apples")).to_be_checked()
    field.fill("app")
    page.get_by_role("list", name="Suggestions").get_by_role(
        "button", name="apples"
    ).click()
    expect(page.get_by_text("Restored apples!")).to_be_visible()
    expect(page.get_by_role("checkbox", name="apples")).not_to_be_checked()

    # Keyboard: arrows highlight a suggestion, Enter picks it, Escape closes.
    suggestions = page.get_by_role("list", name="Suggestions")
    field.fill("a")
    field.press("Escape")
    expect(suggestions).to_be_hidden()
    field.fill("bre")
    field.press("ArrowDown")
    field.press("Enter")
    expect(page.get_by_text("'bread' is already on the list")).to_be_visible()

    # Quantity: shown from Options; "Less" is disabled at 1.
    page.get_by_role("button", name="Options").click()
    page.get_by_role("switch", name="Show quantities").check()
    quantity = page.get_by_role("group", name="Quantity of milk")
    page.get_by_role("button", name="More milk").click()
    expect(quantity).to_contain_text("2")
    page.get_by_role("button", name="More milk").click()
    expect(quantity).to_contain_text("3")
    page.get_by_role("button", name="Less milk").click()
    expect(quantity).to_contain_text("2")
    expect(page.get_by_role("button", name="Less apples")).to_be_disabled()

    # A click inside the dialog (also on its edge) keeps it; outside closes it.
    dialog = page.get_by_role("dialog")
    page.get_by_role("button", name="milk", exact=True).click()
    expect(dialog).to_be_visible()
    # No field has focus, so a phone keyboard stays closed.
    expect(dialog).to_be_focused()
    dialog.click(position={"x": 4, "y": 4})
    expect(dialog).to_be_visible()
    page.mouse.click(4, 4)
    expect(dialog).to_be_hidden()

    # Edit: a duplicate name is refused; name, notes and quantity save together.
    page.get_by_role("button", name="milk", exact=True).click()
    expect(dialog.get_by_label("Item Name")).to_have_value("milk")
    dialog.get_by_label("Item Name").fill("Apples")
    dialog.get_by_role("button", name="Save").click()
    expect(page.get_by_text("'apples' already exists")).to_be_visible()
    expect(dialog).to_be_visible()
    dialog.get_by_label("Item Name").fill("Oat Milk")
    dialog.get_by_label("Description / Notes").fill("lactose free")
    dialog.get_by_role("button", name="More").click()
    expect(dialog.locator("output")).to_have_text("3")
    dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role("group", name="Quantity of oat milk")).to_contain_text("3")
    expect(page.get_by_role("button", name="oat milk (has notes)")).to_be_visible()

    # Delete with Undo.
    page.get_by_role("button", name="Delete bread").click()
    expect(page.get_by_text("Deleted bread")).to_be_visible()
    expect(item_names(page)).to_have_text(["apples", re.compile("^oat milk")])
    page.get_by_role("button", name="Undo").click()
    expect(page.get_by_text("Restored bread")).to_be_visible()
    expect(item_names(page)).to_have_text(["apples", "bread", re.compile("^oat milk")])

    assert server.query(
        "SELECT name, quantity, COALESCE(description, ''), done FROM items ORDER BY name"
    ) == [
        ("apples", 1, "", 0),
        ("bread", 1, "", 0),
        ("oat milk", 3, "lactose free", 0),
    ]


def saved_op(response) -> bool:
    """True for a successful write (op) response from the API."""
    return (
        response.request.method == "POST"
        and response.url.endswith("/ops")
        and response.ok
    )


def test_tags_filter_and_hide_done(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    for name in ("milk", "bread", "apples", "eggs"):
        add_item(page, name)
    expect(item_names(page)).to_have_count(4)

    # Add two list tags in Options mode.
    page.get_by_role("button", name="Options").click()
    tag_field = page.get_by_label("Add Tag")
    tag_field.fill(" Market ")
    tag_field.press("Enter")
    expect(tag_field).to_have_value("")
    tag_field.fill("Lidl")
    page.get_by_role("button", name="Add new tag").click()
    chips = page.get_by_role("list", name="Tags")
    expect(
        chips.get_by_role("button", name=re.compile("^(Lidl|Market)$"))
    ).to_have_text(["Lidl", "Market"])

    # Tag items with the round letter buttons.
    milk_lidl = page.get_by_role("button", name="Lidl tag for milk")
    expect(milk_lidl).to_have_attribute("aria-pressed", "false")
    milk_lidl.click()
    expect(milk_lidl).to_have_attribute("aria-pressed", "true")
    page.get_by_role("button", name="Lidl tag for eggs").click()
    expect(page.get_by_role("button", name="Lidl tag for eggs")).to_have_attribute(
        "aria-pressed", "true"
    )

    # Filter by a tag, then tap it again to show everything.
    page.get_by_role("button", name="Done").click()
    lidl = chips.get_by_role("button", name="Lidl", exact=True)
    lidl.click()
    expect(lidl).to_have_attribute("aria-pressed", "true")
    expect(item_names(page)).to_have_text(["eggs", "milk"])
    lidl.click()
    expect(item_names(page)).to_have_count(4)

    # Delete a tag with Undo; item tags come back with it.
    page.get_by_role("button", name="Options").click()
    page.get_by_role("button", name="Delete tag Lidl").click()
    expect(page.get_by_text("Deleted tag Lidl")).to_be_visible()
    expect(page.get_by_role("button", name="Lidl tag for milk")).to_have_count(0)
    page.get_by_role("button", name="Undo").click()
    expect(page.get_by_text("Restored tag Lidl")).to_be_visible()
    expect(page.get_by_role("button", name="Lidl tag for milk")).to_have_attribute(
        "aria-pressed", "true"
    )

    # An exact duplicate warns; another letter case is a new tag.
    tag_field.fill("Lidl")
    tag_field.press("Enter")
    expect(page.get_by_text("'Lidl' is already a tag")).to_be_visible()
    expect(tag_field).to_have_value("")
    tag_field.fill("lidl")
    tag_field.press("Enter")
    expect(chips.get_by_role("button", name="lidl", exact=True)).to_be_visible()

    # Hide-done "All": checked items disappear; switching it off shows them.
    hide = page.get_by_role("switch", name="Hide checked-off items")
    expect(hide).not_to_be_checked()
    with page.expect_response(saved_op):
        page.get_by_role("checkbox", name="apples").check()
    expect(page.get_by_role("checkbox", name="apples")).to_be_checked()
    # The switch updates the screen at once and saves in the background.
    # Wait for the save before reloading, or the reload can cancel it.
    with page.expect_response(saved_op):
        hide.check()
    expect(page.get_by_role("radio", name="All")).to_be_checked()
    expect(item_names(page)).to_have_text(["bread", "eggs", "milk"])
    page.reload()
    expect(item_names(page)).to_have_text(["bread", "eggs", "milk"])
    page.get_by_role("button", name="Options").click()
    page.get_by_role("switch", name="Hide checked-off items").uncheck()
    expect(item_names(page)).to_have_text(["bread", "eggs", "milk", "apples"])

    [(tags, mode)] = server.query("SELECT list_tags, hide_done_mode FROM lists")
    assert sorted(json.loads(tags)) == ["Lidl", "Market", "lidl"]
    assert mode == "off"
