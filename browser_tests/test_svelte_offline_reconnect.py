"""Reconnect, revocation and resume rules for read-only saved views.

Network loss is simulated by failing every API call (`go_offline`); other faults
use `page.route`. A second browser context plays "another device".
"""

import json
import re

import pytest
from playwright.sync_api import Page, expect
from svelte_app import PHONE, add_item, create_list, item_names, room_app_url, sign_in
from test_svelte_offline import share_link
from test_svelte_share import RESET_MESSAGE, UNAVAILABLE_MESSAGE, reset_link

# Playwright cannot intercept API calls of a worker-controlled page in WebKit,
# and the worker never handles /api, so these tests run without it.
NO_WORKER = {**PHONE, "service_workers": "block"}
RESUME = {
    "visibilitychange": """() => {
        const set = (state) => {
            Object.defineProperty(document, 'visibilityState', {
                configurable: true, get: () => state
            });
            document.dispatchEvent(new Event('visibilitychange'));
        };
        set('hidden');
        set('visible');
    }""",
    # A page restored from the back/forward cache.
    "pageshow": """() => window.dispatchEvent(
        new PageTransitionEvent('pageshow', { persisted: true })
    )""",
}
SAVED = "Saved view — may be out of date."
SLOW = {"timeout": 20_000}  # revalidation retries back off: 1 s, 2 s, 5 s, ...


def saved_notice(page: Page):
    return page.get_by_text(SAVED, exact=False)


def member_with_list(open_session, server, role: str, items=("milk", "bread")):
    """A signed-in page on a list that has `items`."""
    page = open_session(role, **NO_WORKER)
    sign_in(page, server)
    url = create_list(page, "Groceries")
    for name in items:
        add_item(page, name)
    return page, url


API = "**/api/v1/**"


def go_offline(page: Page) -> None:
    """Every API call fails to connect (`set_offline` breaks WebKit navigation)."""
    page.context.route(API, lambda route: route.abort())


def go_online(page: Page) -> None:
    """The API works again; the browser's online event nudges the app."""
    page.context.unroute(API)
    nudge(page)


def nudge(page: Page) -> None:
    page.evaluate("window.dispatchEvent(new Event('online'))")


def view_offline(page: Page, url: str) -> None:
    """Close the network, then open `url` from the saved view."""
    go_offline(page)
    page.goto(url)
    expect(saved_notice(page)).to_be_visible()
    expect(page.get_by_role("button", name="Add")).to_be_disabled()


def count_requests(page: Page, pattern: str) -> list[str]:
    seen: list[str] = []
    page.on(
        "request", lambda r: seen.append(r.url) if re.search(pattern, r.url) else None
    )
    return seen


def test_online_typing_only_suggests_and_never_filters(svelte_server, open_session):
    page, _ = member_with_list(open_session, svelte_server, "typist")
    page.get_by_role("checkbox", name="milk").check()
    page.get_by_role("button", name="Options").click()
    page.get_by_role("switch", name="Hide checked-off items").check()
    page.get_by_role("button", name="Done").click()
    expect(item_names(page)).to_have_text(["bread"])

    field = page.get_by_label("Add or Search")
    field.fill("mil")
    # Suggestions may show, but the list keeps its hide-done view.
    expect(item_names(page)).to_have_text(["bread"])
    field.fill("b")
    expect(item_names(page)).to_have_text(["bread"])
    field.fill("zzz")
    expect(item_names(page)).to_have_text(["bread"])


def test_typing_during_an_online_revalidation_does_not_filter(
    svelte_server, open_session
):
    page, _ = member_with_list(open_session, svelte_server, "typist")
    held = []
    page.route(
        "**/api/v1/rooms/*/session",
        lambda route: held.append(route) if not held else route.continue_(),
    )
    # A resume (as after a back/forward cache restore) revalidates while online;
    # writes stay off until it answers, but the data is not a saved view.
    with page.expect_request(lambda r: r.url.endswith("/session")):
        page.evaluate(RESUME["pageshow"])
    expect(page.get_by_role("button", name="Add")).to_be_disabled()
    expect(saved_notice(page)).to_have_count(0)

    field = page.get_by_label("Add or Search")
    field.fill("zzz")
    expect(item_names(page)).to_have_text(["bread", "milk"])

    held[0].continue_()
    expect(page.get_by_role("button", name="Add")).to_be_enabled()
    field.fill("")


def test_reconnect_needs_validation_and_feed_then_shows_other_devices_changes(
    svelte_server, open_session
):
    server = svelte_server
    page, url = member_with_list(open_session, server, "device-a")
    other = open_session("device-b", **NO_WORKER)
    sign_in(other, server)
    other.get_by_role("link", name="Groceries").click()
    expect(item_names(other)).to_have_text(["bread", "milk"])

    view_offline(page, url)
    expect(item_names(page)).to_have_text(["bread", "milk"])

    # Another device adds an item and deletes one while this one is offline.
    add_item(other, "eggs")
    other.get_by_role("button", name="Options").click()
    other.get_by_role("button", name="Delete bread").click()
    other.get_by_role("button", name="Done").click()
    expect(item_names(other)).to_have_text(["eggs", "milk"])

    # Online again, but the feed is blocked: the online signal alone is not
    # enough to enable writes.
    blocked = count_requests(page, r"/changes")
    page.route("**/api/v1/rooms/*/changes*", lambda route: route.abort())
    with page.expect_request(lambda r: "/changes" in r.url, **SLOW):
        go_online(page)
    page.wait_for_timeout(500)
    assert blocked
    expect(saved_notice(page)).to_be_visible()
    expect(page.get_by_role("button", name="Add")).to_be_disabled()
    expect(page.get_by_role("checkbox", name="milk")).to_be_disabled()
    expect(item_names(page)).to_have_text(["bread", "milk"])

    # Feed back: stale data is replaced and writes come back, with no reload.
    page.unroute("**/api/v1/rooms/*/changes*")
    nudge(page)
    expect(page.get_by_role("checkbox", name="milk")).to_be_enabled(**SLOW)
    expect(item_names(page)).to_have_text(["eggs", "milk"])
    expect(saved_notice(page)).to_have_count(0)
    expect(page.get_by_role("button", name="Add")).to_be_enabled()


def test_revoked_password_clears_saved_room_on_reconnect(svelte_server, open_session):
    server = svelte_server
    page, url = member_with_list(open_session, server, "revoked")
    desktop = open_session("changer", **NO_WORKER)
    sign_in(desktop, server)
    view_offline(page, url)

    desktop.get_by_role("button", name="Room menu").click()
    desktop.get_by_role("button", name="Change Password").click()
    desktop.get_by_label("Current Password").fill(server.password)
    desktop.get_by_label("New Password").fill("new-room-password")
    desktop.get_by_role("button", name="Change").click()
    expect(desktop.get_by_role("heading", name="Home")).to_be_visible()

    go_online(page)
    expect(page.get_by_label("Room Password")).to_be_visible(**SLOW)
    expect(page.get_by_text("milk")).to_have_count(0)

    # The saved data is gone, not just hidden: offline again shows none.
    go_offline(page)
    page.goto(url)
    expect(page.get_by_text("Connect to load this list.")).to_be_visible()
    expect(page.get_by_text("milk")).to_have_count(0)
    expect(saved_notice(page)).to_have_count(0)


def test_reset_share_link_clears_only_that_saved_share(svelte_server, open_session):
    server = svelte_server
    page, list_url = member_with_list(open_session, server, "share-viewer")
    link = share_link(page)
    page.goto(link)
    expect(item_names(page)).to_have_text(["bread", "milk"])
    other = open_session("resetter", **NO_WORKER)
    sign_in(other, server)
    other.get_by_role("link", name="Groceries").click()

    view_offline(page, link)
    expect(item_names(page)).to_have_text(["bread", "milk"])
    reset_link(other)

    go_online(page)
    expect(
        page.get_by_text(re.compile(f"{RESET_MESSAGE}|{UNAVAILABLE_MESSAGE}"))
    ).to_be_visible(**SLOW)
    expect(page.get_by_text("milk")).to_have_count(0)
    expect(page.get_by_label("Add or Search")).to_have_count(0)

    # The old link's saved data is gone; the room's own saved view is separate.
    go_offline(page)
    page.goto(link)
    expect(page.get_by_text("Connect to load this shared list.")).to_be_visible()
    expect(page.get_by_text("milk")).to_have_count(0)
    page.goto(list_url)
    expect(item_names(page)).to_have_text(["bread", "milk"])


def test_network_failure_and_5xx_on_revalidation_keep_the_snapshot(
    svelte_server, open_session
):
    server = svelte_server
    page, url = member_with_list(open_session, server, "flaky")
    view_offline(page, url)

    def stays_saved() -> None:
        page.wait_for_timeout(500)
        expect(saved_notice(page)).to_be_visible()
        expect(item_names(page)).to_have_text(["bread", "milk"])
        expect(page.get_by_role("button", name="Add")).to_be_disabled()

    # The network is back (the event fires) but every API call still fails.
    go_online(page)
    page.route(API, lambda route: route.abort())
    nudge(page)
    stays_saved()

    # The server answers 503 to every API call.
    page.unroute(API)
    page.route(
        API,
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps({"error": {"code": "unavailable", "message": "busy"}}),
        ),
    )
    with page.expect_request(lambda r: "/api/v1/" in r.url, **SLOW):
        nudge(page)
    stays_saved()

    page.unroute(API)
    nudge(page)
    expect(page.get_by_role("button", name="Add")).to_be_enabled(**SLOW)


@pytest.mark.parametrize("signal", ["visibilitychange", "pageshow"])
def test_foreground_resume_revalidates(svelte_server, open_session, signal):
    server = svelte_server
    page, _ = member_with_list(open_session, server, "resumer")
    other = open_session("resume-peer", **NO_WORKER)
    sign_in(other, server)
    other.get_by_role("link", name="Groceries").click()
    # The page's live stream never answers, so only a resume can refresh it.
    page.route("**/api/v1/rooms/*/events", lambda route: None)
    page.reload()
    expect(item_names(page)).to_have_text(["bread", "milk"])
    add_item(other, "eggs")

    sessions = count_requests(page, r"/rooms/[^/]+/session$")
    changes = count_requests(page, r"/changes")
    before = (len(sessions), len(changes))
    page.evaluate(RESUME[signal])
    expect(item_names(page)).to_have_text(["bread", "eggs", "milk"])
    assert len(sessions) > before[0]
    assert len(changes) > before[1]


def test_server_errors_without_a_snapshot_do_not_say_connect(
    svelte_server, open_session
):
    server = svelte_server
    member = open_session("signed-in", **NO_WORKER)
    sign_in(member, server)
    cookies = member.context.cookies()
    # Same cookie, but a new browser profile: signed in, no saved snapshot.
    page = open_session(
        "no-snapshot", storage_state={"cookies": cookies, "origins": []}, **NO_WORKER
    )
    page.route(
        "**/api/v1/rooms/*/changes*",
        lambda route: route.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps({"error": {"code": "server_error", "message": "boom"}}),
        ),
    )
    page.goto(room_app_url(server))
    expect(page.get_by_text("Could not load this room.")).to_be_visible()
    expect(page.get_by_text("Connect to load this room.")).to_have_count(0)
