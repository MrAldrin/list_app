"""Shared steps for the Svelte browser tests (`test_svelte_*.py`)."""

import re
from collections.abc import Callable

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


def admin_sign_in(page, server) -> None:
    page.get_by_label("Admin Password").fill(server.password)
    page.get_by_role("button", name="Log in").click()
    expect(page.get_by_role("button", name="Create New Room")).to_be_visible()
