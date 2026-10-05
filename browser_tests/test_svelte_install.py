"""Svelte home-screen install: the manifest link per page and the install help.

The room page links its room's manifest, so a new icon opens that room; every
other page links the default manifest, which opens the start page. Client-side
navigation changes the one link. See docs/home-screen-installation.md.
"""

import re

from playwright.sync_api import Page, expect
from svelte_app import PHONE, app_url, create_list, room_app_url, sign_in

MANIFEST = 'link[rel="manifest"]'


def absolute(page: Page, href: str) -> str:
    return page.evaluate("(href) => new URL(href, location.href).href", href)


def linked_manifest(page: Page) -> dict:
    """Fetch the page's one manifest the way the browser would."""
    expect(page.locator(MANIFEST)).to_have_count(1)
    href = page.locator(MANIFEST).get_attribute("href")
    response = page.request.get(absolute(page, href))
    assert response.ok
    assert response.headers["content-type"] == "application/manifest+json"
    return response.json()


def expect_manifest(page: Page, href: str) -> None:
    expect(page.locator(MANIFEST)).to_have_count(1)
    expect(page.locator(MANIFEST)).to_have_attribute("href", href)


def test_manifest_follows_the_page(svelte_server, open_session):
    server = svelte_server
    slug = server.room_slug
    page = open_session("phone", **PHONE)

    # The start page: the icon opens the start page (and so the last room).
    page.goto(app_url(server))
    expect_manifest(page, "/app/manifest.webmanifest")
    manifest = linked_manifest(page)
    assert manifest["start_url"] == "/app/"
    assert (manifest["id"], manifest["scope"], manifest["name"]) == ("/", "/", "ListR")

    # The password prompt already links the room manifest; `?admin=true` and
    # the room name never go into it.
    page.goto(room_app_url(server) + "?admin=true")
    expect(page.get_by_label("Room Password")).to_be_visible()
    expect_manifest(page, f"/app/room-manifest/{slug}.webmanifest")
    manifest = linked_manifest(page)
    assert manifest["start_url"] == f"/app/room/{slug}"
    assert manifest["id"] == "/"
    text = str(manifest)
    assert "admin" not in text
    assert "Home" not in text

    # Signed in, then into a list and back, without a page load.
    sign_in(page, server)
    expect_manifest(page, f"/app/room-manifest/{slug}.webmanifest")
    create_list(page, "Groceries")
    expect_manifest(page, "/app/manifest.webmanifest")
    page.go_back()
    expect(page).to_have_url(re.compile(rf"/app/room/{slug}$"))
    expect_manifest(page, f"/app/room-manifest/{slug}.webmanifest")


def test_page_declares_the_home_screen_icon(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    page.goto(app_url(svelte_server))
    icon = page.locator('link[rel="apple-touch-icon"]')
    # Some engines report the attribute as a full address.
    expect(icon).to_have_attribute(
        "href", re.compile(r"^(https?://[^/]+)?/static/icons/apple-touch-icon\.png$")
    )
    response = page.request.get(absolute(page, icon.get_attribute("href")))
    assert response.ok
    assert response.headers["content-type"] == "image/png"
    expect(page.locator('meta[name="apple-mobile-web-app-capable"]')).to_have_count(1)


def test_room_menu_shows_install_help(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Add to Home Screen").click()
    dialog = page.get_by_role("dialog", name="Add ListR to your home screen")
    expect(dialog).to_be_visible()
    for text in (
        "Safari recommended",
        "Chrome recommended",
        "Open as Web App",
        "Install app",
        "install while viewing your room, not a list",
        "one app identity",
    ):
        expect(dialog.get_by_text(text)).to_be_visible()
    # Long help scrolls inside the dialog on a phone; Close is reachable.
    dialog.get_by_role("button", name="Close").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
