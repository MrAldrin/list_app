"""Integrated offline viewing through the installed worker and IndexedDB."""

import re

from playwright.sync_api import Page, expect
from svelte_app import PHONE, add_item, create_list, item_names, room_app_url, sign_in


def start_heading(page: Page):
    """The start page form: proves the app finished starting before a page closes.

    Closing a page mid-startup aborts its lazy route imports, which Firefox
    reports as an unhandled "error loading dynamically imported module".
    """
    return page.get_by_role("heading", name="Open your room link to continue")


def controlled_page(page: Page, url: str) -> tuple[Page, dict[str, bool]]:
    """Install the real app worker, then reopen in a controlled page."""
    page.goto(url)
    expect(start_heading(page)).to_be_visible()
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    capabilities = page.evaluate(
        """() => ({
            secureContext: isSecureContext,
            locks: Boolean(navigator.locks),
            broadcastChannel: typeof BroadcastChannel === 'function'
        })"""
    )
    assert capabilities["secureContext"]
    assert capabilities["broadcastChannel"]
    context = page.context
    page.close()
    page = context.new_page()
    page.goto(url)
    expect(start_heading(page)).to_be_visible()
    page.wait_for_function(
        "navigator.serviceWorker.controller?.scriptURL.endsWith('/service-worker.js')"
    )
    return page, capabilities


def share_link(page: Page) -> str:
    page.get_by_role("button", name="List menu").click()
    page.get_by_role("button", name="Share List").click()
    dialog = page.get_by_role("dialog")
    link = dialog.get_by_role("textbox", name="Link").input_value()
    dialog.get_by_role("button", name="Close").click()
    return link


def test_saved_room_and_share_views_are_read_only_offline(svelte_server, open_session):
    server = svelte_server
    page, capabilities = controlled_page(
        open_session("offline-member", **PHONE), server.url
    )
    print(f"secure localhost browser capabilities: {capabilities}")
    sign_in(page, server)
    list_url = create_list(page, "Groceries")
    for name in ("apples", "milk", "bread"):
        add_item(page, name)

    page.get_by_role("button", name="Options").click()
    tag = page.get_by_label("Add Tag")
    tag.fill("Market")
    tag.press("Enter")
    page.get_by_role("button", name="Market tag for apples").click()
    page.get_by_role("button", name="Market tag for milk").click()
    with page.expect_response(
        lambda response: (
            response.request.method == "POST" and response.url.endswith("/ops")
        )
    ):
        page.get_by_role("checkbox", name="milk").check()
    with page.expect_response(
        lambda response: (
            response.request.method == "POST" and response.url.endswith("/ops")
        )
    ):
        page.get_by_role("switch", name="Hide checked-off items").check()
    page.get_by_role("button", name="Done").click()

    public_url = share_link(page)
    page.goto(public_url)
    expect(page.get_by_role("heading", name="Groceries")).to_be_visible()
    page.goto(list_url)

    # A second installed device has a shell but no saved list data.
    empty, _ = controlled_page(open_session("offline-no-data", **PHONE), server.url)
    empty.goto(f"{server.url}/room/unknown-room")
    expect(empty.get_by_label("Room Password")).to_be_visible()
    root_only, _ = controlled_page(
        open_session("offline-root-no-data", **PHONE), server.url
    )

    server.stop()
    expect(
        page.get_by_text("Saved view — may be out of date.", exact=False)
    ).to_be_visible()

    # Search can reveal saved checked items without changing shared state.
    field = page.get_by_label("Add or Search")
    field.fill("milk")
    expect(item_names(page)).to_have_text(["milk"])
    expect(page.get_by_role("button", name="Add")).to_be_disabled()
    expect(page.get_by_role("checkbox", name="milk")).to_be_disabled()
    expect(page.get_by_role("button", name="Market tag for milk")).to_be_disabled()
    field.fill("")
    expect(item_names(page)).to_have_text(["apples", "bread"])

    page.get_by_role("button", name="Options").click()
    expect(page.get_by_role("switch", name="Hide checked-off items")).to_be_disabled()
    expect(page.get_by_role("button", name="Add new tag")).to_be_disabled()
    expect(page.get_by_role("button", name="Delete tag Market")).to_be_disabled()
    expect(page.get_by_role("button", name="Delete apples")).to_be_disabled()
    page.get_by_role("switch", name="Show quantities").check()
    page.get_by_role("button", name="Done").click()
    field.fill("milk")
    expect(page.get_by_role("button", name="More milk")).to_be_disabled()
    field.blur()
    page.get_by_role("button", name="milk", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Item Name").fill("unsaved draft")
    expect(dialog.get_by_role("button", name="Save")).to_be_disabled()
    expect(dialog.get_by_role("button", name="Delete Item")).to_be_disabled()
    expect(dialog.get_by_label("Item Name")).to_have_value("unsaved draft")
    dialog.get_by_role("button", name="Cancel").click()
    field.fill("")
    market = page.get_by_role("button", name="Market", exact=True)
    market.click()
    expect(item_names(page)).to_have_text(["apples"])
    market.click()
    expect(item_names(page)).to_have_text(["apples", "bread"])

    # Private room management is disabled, but local logout remains available.
    room_page = page.context.new_page()
    room_page.goto(room_app_url(server))
    expect(room_page.get_by_role("heading", name="Home")).to_be_visible()
    expect(room_page.get_by_role("button", name="Add New List")).to_be_disabled()
    for name in ("Rename Groceries", "Delete Groceries"):
        expect(room_page.get_by_role("button", name=name)).to_be_disabled()
    room_page.get_by_role("button", name="Room menu").click()
    for name in ("Rename Room", "Change Password", "Delete Room"):
        expect(room_page.get_by_role("button", name=name)).to_be_disabled()
    expect(room_page.get_by_role("button", name="Log out")).to_be_enabled()

    # A separate page lets the saved room hint route / back to the room.
    member_root = page.context.new_page()
    member_root.goto(server.url)
    expect(member_root).to_have_url(re.compile(rf"/room/{server.room_slug}$"))
    expect(member_root.get_by_role("heading", name="Home")).to_be_visible()

    # Public share snapshots are separate and never restore room-member UI.
    share_page = page.context.new_page()
    share_page.goto(public_url)
    expect(share_page.get_by_role("heading", name="Groceries")).to_be_visible()
    expect(
        share_page.get_by_text("Saved view — may be out of date.", exact=False)
    ).to_be_visible()
    expect(share_page.get_by_role("link", name="Back to room")).to_have_count(0)
    share_page.get_by_role("button", name="List menu").click()
    expect(share_page.get_by_role("button", name="Reset share link")).to_have_count(0)

    # Shell-only room and share URLs report Connect, not a permanent spinner.
    empty.goto(f"{server.url}/room/unknown-room")
    expect(empty.get_by_text("Connect to load this room.")).to_be_visible()
    empty.goto(f"{server.url}/share/{'x' * 43}")
    expect(empty.get_by_text("Connect to load this shared list.")).to_be_visible()
    root_only.on("weberror", lambda error: print("root-only-error", error.error))
    root_only.reload()
    expect(
        root_only.get_by_text("Connect to load a saved room", exact=False)
    ).to_be_visible()

    assert server.query("SELECT name FROM items ORDER BY name") == [
        ("apples",),
        ("bread",),
        ("milk",),
    ]

    # Reconnection alone is not authority; this new load revalidates session and feed.
    server.start()
    page.goto(f"{list_url}?reopen=after-offline")
    expect(page.get_by_role("button", name="Add")).to_be_enabled()
    expect(
        page.get_by_text("Saved view — may be out of date.", exact=False)
    ).to_have_count(0)


def test_offline_logout_clears_room_but_keeps_share_and_marker(
    svelte_server, open_session
):
    server = svelte_server
    page, capabilities = controlled_page(
        open_session("logout-member", **PHONE), server.url
    )
    print(f"secure localhost browser capabilities: {capabilities}")
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    public_url = share_link(page)
    page.goto(public_url)
    expect(page.get_by_role("link", name="Back to room")).to_be_visible()

    peer = page.context.new_page()
    peer.goto(room_app_url(server))
    peer.wait_for_function(
        "navigator.serviceWorker.controller?.scriptURL.endsWith('/service-worker.js')"
    )
    expect(peer.get_by_role("heading", name="Home")).to_be_visible()

    server.stop()
    peer.get_by_role("button", name="Room menu").click()
    peer.get_by_role("button", name="Log out").click()
    expect(peer.get_by_text(re.compile("cookie may still work", re.I))).to_be_visible()
    expect(peer.get_by_label("Room Password")).to_be_visible()
    expect(page.get_by_role("link", name="Back to room")).to_have_count(0)
    page.get_by_role("button", name="List menu").click()
    expect(page.get_by_role("button", name="Reset share link")).to_have_count(0)
    expect(item_names(page)).to_have_text(["milk"])

    peer.reload()
    expect(peer.get_by_label("Room Password")).to_be_visible()
    peer.get_by_label("Room Password").fill(server.password)
    peer.get_by_role("button", name="Enter").click()
    expect(peer.get_by_role("alert")).to_contain_text(
        re.compile("pending sign-out|sign-out state", re.I)
    )
    expect(item_names(peer)).to_have_count(0)

    page.reload()
    expect(page.get_by_role("heading", name="Groceries")).to_be_visible()
    expect(
        page.get_by_text("Saved view — may be out of date.", exact=False)
    ).to_be_visible()
    expect(page.get_by_role("link", name="Back to room")).to_have_count(0)

    server.start()
    peer.get_by_label("Room Password").fill(server.password)
    peer.get_by_role("button", name="Enter").click()
    expect(peer.get_by_role("heading", name="Home")).to_be_visible()
    expect(peer.get_by_role("button", name="Add New List")).to_be_enabled()
    assert server.query("SELECT name FROM items") == [("milk",)]


def test_legacy_private_list_route_opens_from_room_snapshot_offline(
    svelte_server, open_session
):
    server = svelte_server
    page, capabilities = controlled_page(
        open_session("legacy-offline-member", **PHONE), server.url
    )
    print(f"secure localhost browser capabilities: {capabilities}")
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    list_slug = server.query("SELECT slug FROM lists WHERE name = 'Groceries'")[0][0]

    # This second browser context has the app shell but no room/list snapshot.
    empty, _ = controlled_page(
        open_session("legacy-offline-empty", **PHONE), server.url
    )
    server.stop()

    page.goto(f"{server.url}/list/{list_slug}")
    expect(page.get_by_role("heading", name="Groceries")).to_be_visible()
    expect(
        page.get_by_text("Saved view — may be out of date.", exact=False)
    ).to_be_visible()
    expect(item_names(page)).to_have_text(["milk"])
    page.wait_for_timeout(250)

    empty.goto(f"{server.url}/list/{list_slug}")
    expect(
        empty.get_by_text("Connect to open this saved list", exact=False)
    ).to_be_visible()
    empty.wait_for_timeout(250)
