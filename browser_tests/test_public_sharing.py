"""End-to-end sharing against a real app process, on Chromium and Firefox."""

import json
import re

from playwright.sync_api import expect

expect.set_options(timeout=10_000)


class DelayedUpdates:
    """Delay server frames so stale controls can actually be clicked after reset."""

    def __init__(self, page):
        self.paused = False
        self.pending = []
        self.sent_events = []
        page.route_web_socket(re.compile(r".*/_nicegui_ws/socket.io/.*"), self.connect)

    def connect(self, route):
        server = route.connect_to_server()

        def receive(message):
            if self.paused and isinstance(message, str) and message.startswith("4"):
                self.pending.append((route, message))
            else:
                route.send(message)

        def send(message):
            if self.paused and isinstance(message, str) and '"event"' in message:
                self.sent_events.append(message)
            server.send(message)

        server.on_message(receive)
        route.on_message(send)

    def resume(self):
        self.paused = False
        for route, message in self.pending:
            route.send(message)
        self.pending.clear()

    @staticmethod
    def wait_for_server(page):
        # NiceGUI's ack handler ignores an unknown client ID. Its Socket.IO reply
        # is a round-trip barrier after the real, synchronous item click handlers.
        # This prevents checking SQLite before the stale event has been handled.
        page.evaluate("""() => {
            window.testEventHandled = false;
            window.socket.emit('ack', {client_id: ''}, () => {
                window.testEventHandled = true;
            });
        }""")
        page.wait_for_function("window.testEventHandled === true", timeout=10_000)


def create_list(member, server):
    member.goto(server.room_url)
    member.get_by_label("Room Password", exact=True).fill(server.password)
    member.get_by_role("button", name="Enter", exact=True).click()
    member.get_by_role("button", name="Add New List", exact=True).click()
    member.get_by_label("List name", exact=True).fill("Browser groceries")
    member.get_by_role("button", name="Save", exact=True).click()
    expect(member.get_by_text("browser groceries", exact=True)).to_be_visible()
    expect(member).to_have_url(re.compile(r"/list/[^/]+$"))
    return member.url


def share_link(page):
    page.get_by_role("button", name="List menu", exact=True).click()
    page.get_by_text("Share List", exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Share this list", exact=True)).to_be_visible()
    link = dialog.get_by_role("textbox").input_value()
    assert re.search(r"/share/[A-Za-z0-9_-]{43}$", link)
    dialog.get_by_role("button", name="Close", exact=True).click()
    expect(dialog).not_to_be_visible()
    return link


def add_item(page, name):
    page.get_by_label("Add or Search", exact=True).fill(name)
    page.get_by_role("button", name="Add", exact=True).click()
    expect(page.get_by_text(name, exact=True)).to_be_visible()


def reset_link(member):
    member.get_by_role("button", name="List menu", exact=True).click()
    member.get_by_text("Reset share link", exact=True).click()
    dialog = member.get_by_role("dialog")
    expect(dialog.get_by_text("Reset share link?", exact=True)).to_be_visible()
    dialog.get_by_role("button", name="Reset share link", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(member.get_by_label("Add or Search", exact=True)).to_be_visible()


def test_sharing_live_updates_revocation_and_restart(server, sessions):
    member, visitor = sessions
    delayed = DelayedUpdates(visitor)
    private_url = create_list(member, server)
    old_link = share_link(member)
    add_item(member, "milk")

    # The visitor cannot open a legacy URL or discover the new link through it.
    visitor.goto(private_url)
    expect(
        visitor.get_by_text("Room access required to open this list.")
    ).to_be_visible()
    expect(visitor.get_by_text("milk", exact=True)).not_to_be_visible()
    expect(
        visitor.get_by_role("button", name="List menu", exact=True)
    ).not_to_be_visible()
    expect(visitor).to_have_url(private_url)

    visitor.goto(old_link)
    expect(visitor.get_by_text("milk", exact=True)).to_be_visible()
    visitor.get_by_role("button", name="List menu", exact=True).click()
    expect(visitor.get_by_text("Reset share link", exact=True)).to_have_count(0)
    visitor.keyboard.press("Escape")
    add_item(visitor, "bread")
    expect(member.get_by_text("bread", exact=True)).to_be_visible()
    add_item(member, "eggs")
    expect(visitor.get_by_text("eggs", exact=True)).to_be_visible()

    # Keep a public edit dialog open while the member rotates the link.
    visitor.get_by_text("milk", exact=True).click()
    edit = visitor.get_by_role("dialog")
    edit.get_by_label("Item Name", exact=True).fill("forbidden edit")
    delayed.paused = True
    reset_link(member)
    edit.get_by_role("button", name="Save", exact=True).click()
    delayed.resume()
    expect(visitor.get_by_label("Add or Search", exact=True)).not_to_be_visible()
    expect(visitor.get_by_text(re.compile("This list was deleted or"))).to_be_visible()
    delayed.wait_for_server(visitor)
    assert delayed.sent_events, "The stale browser must actually send its edit"
    assert not server.query("SELECT id FROM items WHERE name = 'forbidden edit'")
    assert server.query("SELECT name FROM items WHERE name = 'milk'") == [("milk",)]

    visitor.goto(old_link)
    expect(visitor.get_by_label("Add or Search", exact=True)).not_to_be_visible()
    expect(visitor.get_by_text("milk", exact=True)).not_to_be_visible()
    new_link = share_link(member)
    assert new_link != old_link
    visitor.goto(new_link)
    add_item(visitor, "apples")
    expect(member.get_by_text("apples", exact=True)).to_be_visible()

    # Restart with the same test database, signing key, and browser storage.
    server.restart()
    member.goto(server.url)
    expect(member).to_have_url(server.room_url)
    expect(
        member.get_by_role("button", name="Add New List", exact=True)
    ).to_be_visible()
    expect(member.get_by_label("Room Password", exact=True)).not_to_be_visible()
    member.get_by_role("button", name="browser groceries", exact=True).click()
    expect(member.get_by_text("apples", exact=True)).to_be_visible()
    assert share_link(member) == new_link
    visitor.goto(new_link)
    add_item(visitor, "after restart")
    expect(member.get_by_text("after restart", exact=True)).to_be_visible()
    visitor.goto(old_link)
    expect(visitor.get_by_label("Add or Search", exact=True)).not_to_be_visible()


def test_reset_cancels_public_undo_but_keeps_room_access(server, sessions):
    member, visitor = sessions
    delayed = DelayedUpdates(visitor)
    private_url = create_list(member, server)
    add_item(member, "undo target")
    old_link = share_link(member)
    visitor.goto(old_link)
    visitor.get_by_role("button", name="Options", exact=True).click()
    expect(visitor.get_by_label("Add Tag", exact=True)).to_be_visible()
    visitor.get_by_text("undo target", exact=True).click()
    dialog = visitor.get_by_role("dialog")
    dialog.get_by_role("button").filter(
        has=visitor.locator("i", has_text="delete")
    ).click()
    expect(visitor.get_by_role("button", name="Undo", exact=True)).to_be_visible()
    expect(member.get_by_text("undo target", exact=True)).not_to_be_visible()
    delayed.paused = True
    reset_link(member)
    visitor.get_by_role("button", name="Undo", exact=True).click()
    delayed.resume()
    expect(visitor.get_by_text(re.compile("This list was deleted or"))).to_be_visible()
    expect(visitor.get_by_role("button", name="Undo", exact=True)).not_to_be_visible()
    delayed.wait_for_server(visitor)
    assert delayed.sent_events, "The stale browser must actually send its undo"
    assert not server.query("SELECT id FROM items WHERE name = 'undo target'")
    expect(member).to_have_url(private_url)
    add_item(member, "room still works")
    visitor.goto(server.room_url)
    expect(visitor.get_by_label("Room Password", exact=True)).to_be_visible()


def test_revoked_tab_cannot_add_and_existing_room_tab_keeps_access(server, sessions):
    member, visitor = sessions
    delayed = DelayedUpdates(visitor)
    private_url = create_list(member, server)
    link = share_link(member)
    room_tab = member.context.new_page()
    room_tab.goto(private_url)
    expect(room_tab.get_by_label("Add or Search", exact=True)).to_be_visible()
    visitor.goto(link)
    visitor.get_by_label("Add or Search", exact=True).fill("forbidden add")
    delayed.paused = True
    reset_link(member)
    visitor.get_by_role("button", name="Add", exact=True).click()
    delayed.resume()
    expect(visitor.get_by_text(re.compile("This list was deleted or"))).to_be_visible()
    delayed.wait_for_server(visitor)
    assert delayed.sent_events, "The stale browser must actually send its add"
    assert not server.query("SELECT id FROM items WHERE name = 'forbidden add'")
    add_item(room_tab, "existing room tab")
    expect(member.get_by_text("existing room tab", exact=True)).to_be_visible()


def test_public_visitor_edits_tags_but_cannot_rename_list(server, sessions):
    member, visitor = sessions
    create_list(member, server)
    link = share_link(member)
    member.goto(server.room_url)
    list_card = member.locator(".q-card").filter(
        has=member.get_by_role("button", name="browser groceries", exact=True)
    )
    expect(
        list_card.get_by_role("button").filter(has=member.locator("i", has_text="edit"))
    ).to_be_visible()

    visitor.goto(link)
    expect(visitor.get_by_text("browser groceries", exact=True)).to_be_visible()
    expect(visitor.get_by_label("List Name", exact=True)).to_have_count(0)
    visitor.get_by_role("button", name="List menu", exact=True).click()
    expect(visitor.get_by_text("Reset share link", exact=True)).to_have_count(0)
    visitor.keyboard.press("Escape")
    visitor.get_by_role("button", name="Options", exact=True).click()
    expect(visitor.get_by_label("List Name", exact=True)).to_have_count(0)
    visitor.get_by_label("Add Tag", exact=True).fill("produce")
    visitor.get_by_label("Add Tag", exact=True).press("Enter")
    expect(visitor.get_by_role("button", name="produce", exact=True)).to_be_visible()
    assert json.loads(
        server.query(
            "SELECT list_tags FROM lists WHERE name = ?", ("browser groceries",)
        )[0][0]
    ) == ["produce"]

    tag_row = visitor.get_by_role("button", name="produce", exact=True).locator("..")
    tag_row.get_by_role("button").filter(
        has=visitor.locator("i", has_text="close")
    ).click()
    expect(
        visitor.get_by_role("button", name="produce", exact=True)
    ).not_to_be_visible()
    assert (
        json.loads(
            server.query(
                "SELECT list_tags FROM lists WHERE name = ?", ("browser groceries",)
            )[0][0]
        )
        == []
    )
    assert server.query("SELECT name FROM lists") == [("browser groceries",)]


def test_revoked_room_tab_cannot_save_open_rename_dialog(server, sessions):
    member, _visitor = sessions
    delayed = DelayedUpdates(member)
    create_list(member, server)
    member.goto(server.room_url)
    list_card = member.locator(".q-card").filter(
        has=member.get_by_role("button", name="browser groceries", exact=True)
    )
    list_card.get_by_role("button").filter(
        has=member.locator("i", has_text="edit")
    ).click()
    rename_dialog = member.get_by_role("dialog")
    rename_dialog.get_by_label("List Name", exact=True).fill("forbidden rename")

    revoker = member.context.new_page()
    revoker.goto(server.room_url)
    revoker.get_by_role("button", name="Room menu", exact=True).click()
    revoker.get_by_text("Change Password", exact=True).click()
    password_dialog = revoker.get_by_role("dialog")
    password_dialog.get_by_label("Current Password", exact=True).fill(server.password)
    password_dialog.get_by_label("New Password", exact=True).fill(
        "new-browser-password"
    )
    delayed.paused = True
    password_dialog.get_by_role("button", name="Change", exact=True).click()
    expect(password_dialog).not_to_be_visible()

    # Send Save from the already-open dialog, not just assert that it disappears.
    rename_dialog.get_by_role("button", name="Save", exact=True).click()
    delayed.resume()
    # The invalid-access response navigates only after the server handles Save.
    expect(member).to_have_url(server.room_url)
    assert delayed.sent_events, "The stale browser must actually send its rename"
    assert server.query("SELECT name FROM lists") == [("browser groceries",)]


def test_revoked_public_tab_cannot_save_tag(server, sessions):
    member, visitor = sessions
    delayed = DelayedUpdates(visitor)
    create_list(member, server)
    old_link = share_link(member)
    visitor.goto(old_link)
    visitor.get_by_role("button", name="Options", exact=True).click()
    visitor.get_by_label("Add Tag", exact=True).fill("revoked tag")
    delayed.paused = True
    reset_link(member)
    visitor.get_by_label("Add Tag", exact=True).press("Enter")
    delayed.resume()
    expect(visitor.get_by_text(re.compile("This list was deleted or"))).to_be_visible()
    delayed.wait_for_server(visitor)
    assert delayed.sent_events, "The stale browser must actually send its tag edit"
    assert json.loads(server.query("SELECT list_tags FROM lists")[0][0]) == []
    new_link = share_link(member)
    visitor.goto(new_link)
    visitor.get_by_role("button", name="Options", exact=True).click()
    visitor.get_by_label("Add Tag", exact=True).fill("current tag")
    visitor.get_by_label("Add Tag", exact=True).press("Enter")
    expect(
        visitor.get_by_role("button", name="current tag", exact=True)
    ).to_be_visible()
    assert json.loads(server.query("SELECT list_tags FROM lists")[0][0]) == [
        "current tag"
    ]


def test_cancel_reset_keeps_public_link_working(server, sessions):
    member, visitor = sessions
    create_list(member, server)
    link = share_link(member)
    visitor.goto(link)
    expect(visitor.get_by_label("Add or Search", exact=True)).to_be_visible()
    member.get_by_role("button", name="List menu", exact=True).click()
    member.get_by_text("Reset share link", exact=True).click()
    dialog = member.get_by_role("dialog")
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(dialog).not_to_be_visible()
    assert share_link(member) == link
    add_item(visitor, "reset cancelled")
    expect(member.get_by_text("reset cancelled", exact=True)).to_be_visible()


def test_invalid_tokens_never_render_list_contents(server, sessions):
    member, visitor = sessions
    create_list(member, server)
    add_item(member, "private contents")
    link = share_link(member)
    for invalid in (link[:-1], f"{server.url}/share/{'x' * 43}"):
        visitor.goto(invalid)
        expect(
            visitor.get_by_text(
                "This list was deleted or you no longer have access.", exact=True
            )
        ).to_be_visible()
        expect(visitor.get_by_text("private contents", exact=True)).not_to_be_visible()
        expect(visitor.get_by_label("Add or Search", exact=True)).not_to_be_visible()
