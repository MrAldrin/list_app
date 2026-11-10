"""Shared steps for the Svelte browser tests (`test_svelte_*.py`)."""

import re
import uuid
from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect

expect.set_options(timeout=10_000)

# A phone-sized screen (iPhone 13/14 size). `is_mobile` works only in Chromium.
PHONE = {"viewport": {"width": 390, "height": 844}, "has_touch": True}
DESKTOP = {"viewport": {"width": 1280, "height": 900}}


def app_url(server, path: str = "") -> str:
    return f"{server.url}/{path}"


def room_app_url(server) -> str:
    return app_url(server, f"room/{server.room_slug}")


def sign_in(page: Page, server, password: str | None = None) -> None:
    """Open the room in the Svelte app and enter the password."""
    page.goto(room_app_url(server))
    page.get_by_label("Room Password").fill(password or server.password)
    page.get_by_label("Room Password").press("Enter")
    expect(page.get_by_role("button", name="Add New List")).to_be_visible()


def api_sign_in(page: Page, server, password: str | None = None) -> None:
    """Sign in to the room without the UI; the cookie lands in the page's context.

    Use it for set-up only. The sign-in page itself is tested through the UI.
    """
    response = page.context.request.post(
        f"{server.url}/api/v1/rooms/{server.room_slug}/session",
        data={"password": password or server.password},
        headers={"Origin": server.url},
    )
    assert response.status == 200, response.text()


def _api_op(page: Page, server, op_type: str, **fields: Any) -> dict[str, Any]:
    response = page.context.request.post(
        f"{server.url}/api/v1/rooms/{server.room_slug}/ops",
        data={"op_id": str(uuid.uuid4()), "type": op_type, **fields},
        headers={"Origin": server.url},
    )
    assert response.status == 200, response.text()
    answer = response.json()
    assert answer["status"] == "applied", answer
    return answer["result"]


def api_seed(
    page: Page, server, lists: dict[str, list[str | dict[str, str]]]
) -> dict[str, str]:
    """Create lists and items without the UI; return the list page URLs by name.

    An item is a name, or {"name": ..., "date": "YYYY-MM-DD"}. The page must be
    signed in (`api_sign_in` or `sign_in`). Use it for set-up only: creating a
    list, adding an item and setting a date each keep a test through the UI.
    """
    urls = {}
    for list_name, items in lists.items():
        created = _api_op(page, server, "list.create", name=list_name)
        list_uid = created["list_uid"]
        for item in items:
            fields = {"name": item} if isinstance(item, str) else item
            added = _api_op(
                page, server, "item.add", list_uid=list_uid, name=fields["name"]
            )
            if "date" in fields:
                _api_op(
                    page,
                    server,
                    "item.edit",
                    list_uid=list_uid,
                    item_uid=added["item_uid"],
                    name=fields["name"],
                    description="",
                    date=fields["date"],
                    base_seq=added["changed_seq"],
                )
        urls[list_name] = f"{room_app_url(server)}/list/{created['slug']}"
    return urls


def open_list(page: Page, url: str, name: str) -> None:
    """Open a list page by its URL and wait until it shows the list."""
    page.goto(url)
    expect(page.get_by_role("heading", name=name)).to_be_visible()


def create_list(page: Page, name: str) -> str:
    """Create a list from the room page; return the list page URL."""
    page.get_by_role("button", name="Add New List").click()
    page.get_by_label("List name").fill(name)
    page.get_by_label("List name").press("Enter")
    expect(page).to_have_url(re.compile(r"/room/[^/]+/list/[^/]+$"))
    expect(page.get_by_role("heading", name=name)).to_be_visible()
    return page.url


def add_item(page: Page, name: str) -> None:
    field = page.get_by_label("Add or Search")
    field.fill(name)
    field.press("Enter")
    expect(field).to_have_value("")


def item_names(page: Page):
    return page.locator("ul.items > li .name")


def add_list_tag(page: Page, tag: str) -> None:
    """Add a list tag from Options > Tags, then close the Tags dialog.

    Options stays open (its button then says "Done"), as the callers expect.
    """
    # Options may already be open (its button then says "Done").
    toggle = page.get_by_role("button", name=re.compile(r"^(Options|Done)$"))
    expect(toggle).to_be_visible()
    if toggle.inner_text().strip() == "Options":
        toggle.click()
    page.get_by_role("button", name="Tags").click()
    tags_dialog = page.get_by_role("dialog", name="Tags")
    field = tags_dialog.get_by_label("Add tag")
    field.fill(tag)
    field.press("Enter")
    tags_dialog.get_by_role("button", name="Close").click()


# Offline set-up shared by the offline, conflict and due tests ---------------

# Playwright cannot intercept API calls of a worker-controlled page in WebKit,
# and the worker never handles /api, so these tests run without it.
NO_WORKER = {**PHONE, "service_workers": "block"}
SAVED = "Offline — changes are saved"
SLOW = {"timeout": 20_000}  # revalidation retries back off: 1 s, 2 s, 5 s, ...


def saved_notice(page: Page):
    return page.get_by_text(SAVED, exact=False)


def member_with_list(open_session, server, role: str, items=("milk", "bread")):
    """A signed-in page on a list that has `items`.

    The data is built through the API. The page then loads the room and the
    list online, so it has saved both before a test takes the network away.
    """
    page = open_session(role, **NO_WORKER)
    api_sign_in(page, server)
    url = api_seed(page, server, {"Groceries": list(items)})["Groceries"]
    page.goto(room_app_url(server))
    # A tap on the link, as a user does: a second page load here would cancel
    # the room page's requests while they are in flight.
    page.get_by_role("link", name="Groceries").click()
    expect(page).to_have_url(url)
    expect(page.get_by_role("heading", name="Groceries")).to_be_visible()
    expect(item_names(page)).to_have_text(sorted(items))
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
    expect(page.get_by_role("button", name="Add")).to_be_enabled()


def list_links(page: Page):
    return page.locator("main li a")


SHARE_LINK = re.compile(r"/share/[A-Za-z0-9_-]{43}$")


def share_link(page: Page) -> str:
    page.get_by_role("button", name="List menu").click()
    page.get_by_role("button", name="Share List").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("heading", name="Share this list")).to_be_visible()
    expect(
        dialog.get_by_text("Anyone with this link can open this list.")
    ).to_be_visible()
    link = dialog.get_by_role("textbox", name="Link").input_value()
    assert SHARE_LINK.search(link), link
    dialog.get_by_role("button", name="Close").click()
    expect(dialog).to_have_count(0)
    return link


def hold_live_updates(page: Page) -> None:
    """The page's live stream never connects, so it misses a share reset or a delete.

    Its next write is then sent with the old link, as from a phone that was
    asleep while the link was reset.
    """
    page.live_stream_held = True  # the fixture does not wait for it at close
    page.route(re.compile(r"/api/v1/(rooms|share)/[^/]+/events"), lambda route: None)


def wait_until(
    page: Page,
    check: Callable[[], bool],
    message: str,
    timeout_ms: int = 10_000,
) -> None:
    """Let the page run until `check()` is true, for state only Python can see.

    Use it for what a route handler or the server recorded in Python. Waits on
    the page itself should use `expect` or `wait_for_function`.
    """
    waited = 0
    while not check():
        if waited >= timeout_ms:
            raise AssertionError(message)
        page.wait_for_timeout(100)
        waited += 100


def wait_for_live_stream(page: Page) -> None:
    """Wait until the page's live stream request is in flight.

    A page opens its stream right after it loads. A full reload before that
    cancels the request while the browser is still starting it, and WebKit
    reports the cancel as a page error. Wait until the request is in flight.
    """
    wait_until(
        page,
        lambda: any(r.url.endswith("/events") for r in page.api_pending),
        "The live stream did not start.",
    )


def admin_sign_in(page, server) -> None:
    page.get_by_label("Admin Password").fill(server.password)
    page.get_by_role("button", name="Log in").click()
    expect(page.get_by_role("button", name="Create New Room")).to_be_visible()
