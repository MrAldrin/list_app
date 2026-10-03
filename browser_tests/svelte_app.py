"""Shared steps for the Svelte browser tests (`test_svelte_*.py`)."""

import re

from playwright.sync_api import Page, expect

expect.set_options(timeout=10_000)

# A phone-sized screen (iPhone 13/14 size). `is_mobile` works only in Chromium.
PHONE = {"viewport": {"width": 390, "height": 844}, "has_touch": True}
DESKTOP = {"viewport": {"width": 1280, "height": 900}}


def app_url(server, path: str = "") -> str:
    return f"{server.url}/app/{path}"


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
    expect(page).to_have_url(re.compile(r"/app/room/[^/]+/list/[^/]+$"))
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


def nicegui_sign_in(page: Page, server) -> None:
    """Sign in to the NiceGUI room page (its own login, separate from Svelte)."""
    page.goto(server.room_url)
    page.get_by_label("Room Password", exact=True).fill(server.password)
    page.get_by_role("button", name="Enter", exact=True).click()
    expect(page.get_by_role("button", name="Room menu")).to_be_visible()
