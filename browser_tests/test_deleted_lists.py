"""Stale room and public pages cannot write after another user deletes a list."""

import re

import pytest
from playwright.sync_api import expect
from test_public_sharing import DelayedUpdates, add_item
from test_public_sharing import seeded_list as prepare_list


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
    """Return the real interaction and its specific NiceGUI control."""
    if action == "add":
        page.get_by_label("Add or Search", exact=True).fill("forbidden")
        control = page.get_by_role("button", name="Add", exact=True)
        return control.click, control
    if action == "edit":
        page.get_by_text("milk", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Item Name", exact=True).fill("forbidden")
        control = dialog.get_by_role("button", name="Save", exact=True)
        return control.click, control
    if action == "toggle":
        control = (
            page.get_by_text("milk", exact=True).locator("..").get_by_role("checkbox")
        )
        return control.click, control
    if action == "quantity":
        page.get_by_role("button", name="Options", exact=True).click()
        page.get_by_role("switch").first.click()
        control = (
            page.get_by_text("milk", exact=True)
            .locator("xpath=ancestor::div[contains(@class, 'border-b')][1]")
            .locator("button")
            .filter(has_text="+")
        )
        expect(control).to_be_visible()
        return control.click, control
    if action == "tag":
        page.get_by_role("button", name="Options", exact=True).click()
        control = page.get_by_label("Add Tag", exact=True)
        control.fill("forbidden")
        return lambda: control.press("Enter"), control
    if action == "undo":
        page.get_by_role("button", name="Options", exact=True).click()
        page.get_by_text("milk", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_role("button").filter(
            has=page.locator("i", has_text="delete")
        ).click()
        control = page.get_by_role("button", name="Undo", exact=True)
        expect(control).to_be_visible()
        return control.click, control
    raise AssertionError(action)


def watch_action(page, control):
    """Record outgoing NiceGUI events without depending on Socket.IO wire framing."""
    element_id = control.evaluate(
        "element => Number(element.closest('[id^=c]').id.slice(1))"
    )
    page.evaluate("""() => {
        window.testActionEvents = [];
        window.socket.onAnyOutgoing((name, payload) => {
            if (name === 'event') window.testActionEvents.push(payload);
        });
    }""")
    return element_id


def assert_action_sent(page, element_id, action):
    events = page.evaluate("window.testActionEvents")
    matching = [event for event in events if event.get("id") == element_id]
    if action == "toggle":
        matching = [event for event in matching if event.get("args") == ["true"]]
    elif action == "tag":
        matching = [
            event
            for event in matching
            if any('"key":"Enter"' in arg for arg in event.get("args", []))
        ]
    assert matching, f"The stale {action} control must send its own event; got {events}"


# Each action runs in both engines and on both page roles across the pair.
# Other sharing tests cover public revocation in both engines; keep the distinct
# room-deletion navigation matrix below intact.
@pytest.mark.parametrize(
    "action, chromium_role",
    [
        ("add", "room"),
        ("edit", "public"),
        ("toggle", "room"),
        ("quantity", "public"),
        ("tag", "room"),
        ("undo", "public"),
    ],
    ids=["add", "edit", "toggle", "quantity", "tag", "undo"],
)
def test_stale_page_rejects_actions_after_list_deletion(
    server, sessions, browser, action, chromium_role
):
    other_role = "public" if chromium_role == "room" else "room"
    role = {"chromium": chromium_role, "firefox": other_role}[browser.browser_type.name]
    member, visitor = sessions
    private_url, link = prepare_list(member, server)
    add_item(member, "milk")
    stale = member.context.new_page() if role == "room" else visitor
    delayed = DelayedUpdates(stale)
    stale.goto(private_url if role == "room" else link)
    expect(stale.get_by_text("milk", exact=True)).to_be_visible()
    fire, control = prepare_action(stale, action)
    element_id = watch_action(stale, control)
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
    assert_action_sent(stale, element_id, action)
    if role == "room":
        stale.get_by_role("button", name="Back to room").click()
        expect(stale).to_have_url(server.room_url)
    assert not server.query("SELECT id FROM items WHERE name = 'forbidden'")
    assert not server.query("SELECT id FROM lists WHERE name = 'browser groceries'")


@pytest.mark.parametrize("role", ["room", "public"])
def test_stale_page_after_room_deletion_has_no_room_navigation(server, sessions, role):
    member, visitor = sessions
    private_url, link = prepare_list(member, server)
    add_item(member, "milk")
    stale = member.context.new_page() if role == "room" else visitor
    delayed = DelayedUpdates(stale)
    stale.goto(private_url if role == "room" else link)
    fire, control = prepare_action(stale, "add")
    element_id = watch_action(stale, control)
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
    assert_action_sent(stale, element_id, "add")
    assert not server.query("SELECT id FROM items WHERE name = 'forbidden'")
