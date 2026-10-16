"""Integrated offline viewing through the installed worker and IndexedDB."""

import re

from playwright.sync_api import Page, expect
from svelte_app import (
    PHONE,
    add_item,
    create_list,
    item_names,
    list_links,
    room_app_url,
    share_link,
    sign_in,
    wait_until,
)


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


def test_saved_room_and_share_views_edit_offline_except_online_only_actions(
    svelte_server, open_session
):
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
    expect(page.get_by_text("Offline — changes are saved", exact=False)).to_be_visible()
    # The notice is the only connection message, and its spaces render.
    expect(
        page.get_by_text(
            "Offline — changes are saved on this phone and sent when you're back online."
        )
    ).to_be_visible()
    expect(page.get_by_text("Could not load the latest changes")).to_have_count(0)
    expect(page.get_by_text("Reconnecting…")).to_have_count(0)

    # Search filters the saved items; the item controls are enabled (queued).
    field = page.get_by_label("Add or Search")
    field.fill("milk")
    expect(item_names(page)).to_have_text(["milk"])
    expect(page.get_by_role("button", name="Add")).to_be_enabled()
    expect(page.get_by_role("checkbox", name="milk")).to_be_enabled()
    expect(page.get_by_role("button", name="Market tag for milk")).to_be_enabled()
    field.fill("")
    expect(item_names(page)).to_have_text(["apples", "bread"])

    page.get_by_role("button", name="Options").click()
    expect(page.get_by_role("switch", name="Hide checked-off items")).to_be_enabled()
    expect(page.get_by_role("button", name="Add new tag")).to_be_enabled()
    expect(page.get_by_role("button", name="Delete tag Market")).to_be_enabled()
    expect(page.get_by_role("button", name="Delete apples")).to_be_enabled()
    page.get_by_role("switch", name="Show quantities").check()
    page.get_by_role("button", name="Done").click()
    field.fill("milk")
    expect(page.get_by_role("button", name="More milk")).to_be_enabled()
    field.blur()
    page.get_by_role("button", name="milk", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Item Name").fill("unsaved draft")
    expect(dialog.get_by_role("button", name="Save")).to_be_enabled()
    expect(dialog.get_by_role("button", name="Delete Item")).to_be_enabled()
    expect(dialog.get_by_label("Item Name")).to_have_value("unsaved draft")
    dialog.get_by_role("button", name="Cancel").click()
    field.fill("")
    market = page.get_by_role("button", name="Market", exact=True)
    market.click()
    expect(item_names(page)).to_have_text(["apples"])
    market.click()
    expect(item_names(page)).to_have_text(["apples", "bread"])

    # Creating a list, password and room delete need a connection; renames and
    # the list delete are queued. Local logout remains available.
    room_page = page.context.new_page()
    room_page.goto(room_app_url(server))
    expect(room_page.get_by_role("heading", name="Home")).to_be_visible()
    expect(room_page.get_by_role("button", name="Add New List")).to_be_disabled()
    for name in ("Rename Groceries", "Delete Groceries"):
        expect(room_page.get_by_role("button", name=name)).to_be_enabled()
    room_page.get_by_role("button", name="Room menu").click()
    expect(room_page.get_by_role("button", name="Rename Room")).to_be_enabled()
    for name in ("Change Password", "Delete Room"):
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
        share_page.get_by_text("Offline — changes are saved", exact=False)
    ).to_be_visible()
    expect(share_page.get_by_role("link", name="Back to room")).to_have_count(0)
    share_page.get_by_role("button", name="List menu").click()
    expect(share_page.get_by_role("button", name="Share List")).to_be_disabled()
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
    expect(page.get_by_text("Offline — changes are saved", exact=False)).to_have_count(
        0
    )


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
    expect(page.get_by_text("Offline — changes are saved", exact=False)).to_be_visible()
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
    expect(page.get_by_text("Offline — changes are saved", exact=False)).to_be_visible()
    expect(item_names(page)).to_have_text(["milk"])
    page.wait_for_timeout(250)

    empty.goto(f"{server.url}/list/{list_slug}")
    expect(
        empty.get_by_text("Connect to open this saved list", exact=False)
    ).to_be_visible()
    empty.wait_for_timeout(250)


# Records whether the offline notice was ever put on the page, even briefly.
NOTICE_RECORDER = """
(() => {
    window.__offlineNoticeSeen = false;
    const check = () => {
        if (document.querySelector('.saved-notice')) window.__offlineNoticeSeen = true;
    };
    new MutationObserver(check).observe(document, { childList: true, subtree: true });
    check();
})();
"""


def test_saved_view_notice_does_not_flash_online(svelte_server, open_session):
    """Online, opening a page never shows the offline notice, not even briefly.

    The saved view shows first, then the server answers. Showing the notice
    in between made it flash and push the list down on every page.
    """
    server = svelte_server
    page, _ = controlled_page(open_session("online-no-flash", **PHONE), server.url)
    sign_in(page, server)
    list_url = create_list(page, "Groceries")
    add_item(page, "milk")
    page.add_init_script(NOTICE_RECORDER)
    page.evaluate(NOTICE_RECORDER)

    # Moving between the room and a list, a few times.
    for _ in range(2):
        page.get_by_role("link", name="Back to room").click()
        expect(page.get_by_role("button", name="Add New List")).to_be_visible()
        list_links(page).filter(has_text="Groceries").click()
        expect(item_names(page)).to_have_text(["milk"])
        page.wait_for_timeout(300)
        assert not page.evaluate("window.__offlineNoticeSeen")

    # A fresh start shows the saved view first, then the server's answer.
    for url in (list_url, room_app_url(server)):
        page.goto(url)
        expect(page.get_by_text("Groceries").first).to_be_visible()
        page.wait_for_timeout(2_000)
        assert not page.evaluate("window.__offlineNoticeSeen")

    # The saved view was there: offline, the same start shows the notice.
    server.stop()
    page.goto(list_url)
    expect(page.get_by_text("Offline — changes are saved", exact=False)).to_be_visible()
    expect(item_names(page)).to_have_text(["milk"])
    page.wait_for_timeout(250)


def test_offline_edits_survive_a_reload_and_reach_the_server(
    svelte_server, open_session
):
    server = svelte_server
    page, _ = controlled_page(open_session("offline-editor", **PHONE), server.url)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_item(page, "bread")

    server.stop()
    expect(page.get_by_text("Offline — changes are saved", exact=False)).to_be_visible()
    add_item(page, "eggs")
    page.get_by_role("checkbox", name="milk").check()
    expect(item_names(page)).to_have_text(["bread", "eggs", "milk"])
    expect(page.get_by_text("2 changes waiting to be sent.")).to_be_visible()

    # A reload while still offline keeps both changes on the phone.
    page.reload()
    expect(page.get_by_text("Offline — changes are saved", exact=False)).to_be_visible()
    expect(item_names(page)).to_have_text(["bread", "eggs", "milk"])
    expect(page.get_by_role("checkbox", name="milk")).to_be_checked()
    expect(page.get_by_text("2 changes waiting to be sent.")).to_be_visible()

    # Back online: the changes are sent, and the notice goes away.
    server.start()
    page.evaluate("window.dispatchEvent(new Event('online'))")
    expect(page.get_by_text("Offline — changes are saved", exact=False)).to_have_count(
        0, timeout=30_000
    )
    expected = [("bread", 0), ("eggs", 0), ("milk", 1)]
    wait_until(
        page,
        lambda: server.query("SELECT name, done FROM items ORDER BY name") == expected,
        "the queued changes did not reach the server",
        timeout_ms=20_000,
    )

    # Another device, online, sees the same list.
    peer = open_session("offline-peer", **PHONE)
    sign_in(peer, server)
    peer.get_by_role("link", name="Groceries").click()
    expect(item_names(peer)).to_have_text(["bread", "eggs", "milk"])
    expect(peer.get_by_role("checkbox", name="milk")).to_be_checked()
