"""Stale room and public pages cannot write after another user deletes a list."""

import re

import pytest
from playwright.sync_api import expect
from test_public_sharing import DelayedUpdates, add_item, create_list, share_link


def delete_list(member, server):
    member.goto(server.room_url)
    card = member.locator(".q-card").filter(
        has=member.get_by_role("button", name="browser groceries", exact=True)
    )
    card.get_by_role("button").filter(
        has=member.locator("i", has_text="delete")
    ).click()
    dialog = member.get_by_role("dialog")
    expect(dialog.get_by_text(re.compile("Delete 'browser groceries'"))).to_be_visible()
    dialog.get_by_role("button", name="Delete", exact=True).click()
    expect(dialog).not_to_be_visible()
    assert not server.query("SELECT id FROM lists WHERE name = 'browser groceries'")


def prepare_action(page, action):
    if action == "add":
        page.get_by_label("Add or Search", exact=True).fill("forbidden")
        return lambda: page.get_by_role("button", name="Add", exact=True).click()
    if action == "edit":
        page.get_by_text("milk", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Item Name", exact=True).fill("forbidden")
        return lambda: dialog.get_by_role("button", name="Save", exact=True).click()
    if action == "toggle":
        return lambda: (
            page.get_by_text("milk", exact=True)
            .locator("..")
            .get_by_role("checkbox")
            .click()
        )
    if action == "quantity":
        page.get_by_role("button", name="Options", exact=True).click()
        page.get_by_role("switch").first.click()
        plus = (
            page.get_by_text("milk", exact=True)
            .locator("xpath=ancestor::div[contains(@class, 'border-b')][1]")
            .locator("button")
            .filter(has_text="+")
        )
        expect(plus).to_be_visible()
        return lambda: plus.click()
    if action == "tag":
        page.get_by_role("button", name="Options", exact=True).click()
        page.get_by_label("Add Tag", exact=True).fill("forbidden")
        return lambda: page.get_by_label("Add Tag", exact=True).press("Enter")
    if action == "undo":
        page.get_by_role("button", name="Options", exact=True).click()
        page.get_by_text("milk", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_role("button").filter(
            has=page.locator("i", has_text="delete")
        ).click()
        expect(page.get_by_role("button", name="Undo", exact=True)).to_be_visible()
        return lambda: page.get_by_role("button", name="Undo", exact=True).click()
    raise AssertionError(action)


@pytest.mark.parametrize("role", ["room", "public"])
@pytest.mark.parametrize("action", ["add", "edit", "toggle", "quantity", "tag", "undo"])
def test_stale_page_rejects_actions_after_list_deletion(server, sessions, role, action):
    member, visitor = sessions
    private_url = create_list(member, server)
    add_item(member, "milk")
    link = share_link(member)
    stale = member.context.new_page() if role == "room" else visitor
    delayed = DelayedUpdates(stale)
    stale.goto(private_url if role == "room" else link)
    expect(stale.get_by_text("milk", exact=True)).to_be_visible()
    fire = prepare_action(stale, action)
    delayed.paused = True
    delete_list(member, server)
    fire()
    delayed.resume()
    expect(stale.get_by_label("Add or Search", exact=True)).not_to_be_visible()
    if role == "room":
        expect(stale.get_by_text("This list was deleted.", exact=True)).to_be_visible()
        expect(stale.get_by_role("button", name="Back to room")).to_be_visible()
    else:
        expect(
            stale.get_by_text(re.compile("This list was deleted or"))
        ).to_be_visible()
        expect(stale.get_by_role("button", name="Back to room")).to_have_count(0)
    DelayedUpdates.wait_for_server(stale)
    assert delayed.sent_events, "The stale browser must send an action"
    if role == "room":
        stale.get_by_role("button", name="Back to room").click()
        expect(stale).to_have_url(server.room_url)
    assert not server.query("SELECT id FROM items WHERE name = 'forbidden'")
    assert not server.query("SELECT id FROM lists WHERE name = 'browser groceries'")


@pytest.mark.parametrize("role", ["room", "public"])
def test_stale_page_after_room_deletion_has_no_room_navigation(server, sessions, role):
    member, visitor = sessions
    private_url = create_list(member, server)
    add_item(member, "milk")
    link = share_link(member)
    stale = member.context.new_page() if role == "room" else visitor
    delayed = DelayedUpdates(stale)
    stale.goto(private_url if role == "room" else link)
    fire = prepare_action(stale, "add")
    delayed.paused = True
    member.goto(server.room_url)
    member.get_by_role("button", name="Room menu").click()
    member.get_by_text("Delete Room", exact=True).click()
    dialog = member.get_by_role("dialog")
    dialog.get_by_label("Enter Room Password to Confirm").fill(server.password)
    dialog.get_by_role("button", name="Delete", exact=True).click()
    expect(dialog).not_to_be_visible()
    assert not server.query("SELECT id FROM rooms WHERE name = 'Home'")
    fire()
    delayed.resume()
    expect(stale.get_by_label("Add or Search", exact=True)).not_to_be_visible()
    expect(stale.get_by_role("button", name="Back to room")).to_have_count(0)
    DelayedUpdates.wait_for_server(stale)
    assert delayed.sent_events
    assert not server.query("SELECT id FROM items WHERE name = 'forbidden'")
