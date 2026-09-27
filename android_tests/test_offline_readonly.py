"""Opt-in installed Android Chrome check for the offline feature branch."""

import socket
import sqlite3
import time

from playwright.sync_api import (
    Browser,
    BrowserType,
    Error,
    Page,
    expect,
    sync_playwright,
)

from android_tests.test_android_chrome import (
    adb,
    launch_installed_webapp,
    tap_label,
    visible_text,
    wait_for_text,
)
from android_tests.test_android_chrome import (
    android_server as android_server,
)
from browser_tests.conftest import TestServer


def installed_page(browser: Browser, url: str) -> Page:
    """Find the standalone target, including after Chrome replaces its CDP target."""
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for context in browser.contexts:
            for page in context.pages:
                try:
                    if page.url == url and page.evaluate(
                        "matchMedia('(display-mode: standalone)').matches"
                    ):
                        return page
                except Error:
                    continue
        time.sleep(0.5)
    raise AssertionError("Installed room did not open in a standalone target")


def connect_to_chrome(chromium: BrowserType, port: int) -> Browser:
    """Chrome's debugging socket is briefly unavailable after a force-stop."""
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            return chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=3000)
        except Error:
            time.sleep(0.5)
    raise AssertionError("Chrome debugging socket did not reopen after cold launch")


def test_installed_room_cold_launches_saved_lists_without_network(
    android_server: TestServer,
) -> None:
    """A prepared room remains read-only after Chrome is force-stopped offline."""
    room_slug = android_server.query("SELECT slug FROM rooms WHERE name = 'Home'")[0][0]
    room_id = android_server.query("SELECT id FROM rooms WHERE slug = ?", (room_slug,))[
        0
    ][0]
    with sqlite3.connect(android_server.database) as connection:
        list_id = connection.execute(
            "INSERT INTO lists (name, slug, room_id, list_tags) VALUES (?, ?, ?, ?)",
            ("Groceries", "android-groceries", room_id, '["weekly"]'),
        ).lastrowid
        connection.execute(
            """INSERT INTO items (name, done, list_id, active_tags, description, quantity)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("Apples", 1, list_id, '["fruit"]', "Buy green", 3),
        )
    url = android_server.room_url.replace("127.0.0.1", "localhost")
    adb(
        "shell",
        "am",
        "start",
        "-a",
        "android.intent.action.VIEW",
        "-d",
        url,
        "com.android.chrome",
    )
    # Do not accept Chrome's first-run terms on the user's behalf.
    if "Chrome notifications make things easier" in visible_text():
        adb("shell", "input", "keyevent", "KEYCODE_BACK")
    wait_for_text("Enter Room Password for Home")
    screen = visible_text()
    menu = (
        "Customize and control Google Chrome"
        if "Customize and control Google Chrome" in screen
        else "Update available. More options"
    )
    tap_label(menu)
    if "Add to Home screen" in visible_text():
        tap_label("Add to Home screen")
        tap_label("Install")
    else:
        tap_label("Install app")
    wait_for_text("Install app")
    tap_label("Install")
    wait_for_text("Add to home screen")
    tap_label("Add to home screen")
    launch_installed_webapp(url)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        debug_port = sock.getsockname()[1]
    forward = f"tcp:{debug_port}"
    bridge = f"tcp:{android_server.port}"
    adb("forward", forward, "localabstract:chrome_devtools_remote")
    try:
        with sync_playwright() as playwright:
            browser = connect_to_chrome(playwright.chromium, debug_port)
            try:
                page = installed_page(browser, url)
                page.get_by_label("Room Password", exact=True).fill(
                    android_server.password
                )
                page.get_by_role("button", name="Enter", exact=True).click()
                expect(page.get_by_role("button", name="Add New List")).to_be_visible()
                page.wait_for_function(
                    """async (slug) => {
                        const record = await window.ListROfflineStorage?.readRecord();
                        return navigator.serviceWorker.controller &&
                            record?.snapshot.room.slug === slug &&
                            record.snapshot.lists.some(list =>
                                list.name === 'Groceries' &&
                                list.items.some(item => item.name === 'Apples'));
                    }""",
                    arg=room_slug,
                    timeout=20_000,
                )
                saved_at = page.evaluate(
                    "window.ListROfflineStorage.readRecord().then(r => r.saved_at)"
                )
                assert page.evaluate(
                    "(slug) => Boolean(localStorage.getItem('listapp_room_token_' + slug))",
                    room_slug,
                )
                # Remove every network path: ADB reverse can survive airplane mode,
                # and an existing socket can survive removal of the reverse mapping.
                android_server.stop()
                try:
                    adb("reverse", "--remove", bridge)
                    adb("shell", "cmd", "connectivity", "airplane-mode", "enable")
                    assert (
                        page.evaluate(
                            """async () => {
                            try { await fetch('/manifest.json', {cache: 'no-store'}); return true; }
                            catch (_) { return false; }
                        }"""
                        )
                        is False
                    )
                    # Closing the CDP connection before force-stop avoids relying
                    # on an already-open page or Chrome's previous process.
                    browser.close()
                    # Chrome 124 flushes localStorage asynchronously. Immediately
                    # killing it after fresh login loses even unrelated routing
                    # keys. Allow the backgrounded app to settle before force-stop;
                    # the assertions after relaunch, not this delay, prove access.
                    adb("shell", "input", "keyevent", "KEYCODE_HOME")
                    time.sleep(5)
                    adb("shell", "am", "force-stop", "com.android.chrome")
                    launch_installed_webapp(url)
                    browser = connect_to_chrome(playwright.chromium, debug_port)
                    page = installed_page(browser, url)
                    expect(
                        page.get_by_text("Offline · read only", exact=True)
                    ).to_be_visible(timeout=20_000)
                    assert page.url == url
                    assert page.evaluate(
                        "matchMedia('(display-mode: standalone)').matches"
                    )
                    expect(
                        page.get_by_role("heading", name="Groceries")
                    ).to_be_visible()
                    expect(page.get_by_text("Apples", exact=True)).to_be_visible()
                    expect(page.get_by_text("Buy green", exact=False)).to_be_visible()
                    expect(page.get_by_text("Tags: fruit", exact=False)).to_be_visible()
                    expect(page.get_by_text("quantity 3", exact=False)).to_be_visible()
                    expect(page.get_by_text("Last saved:", exact=False)).to_be_visible()
                    assert (
                        page.evaluate(
                            "window.ListROfflineStorage.readRecord().then(r => r.saved_at)"
                        )
                        == saved_at
                    )
                    assert page.locator(".items li.done").count() == 1
                    assert page.locator("input, button").count() == 0
                    assert page.evaluate(
                        "(slug) => Boolean(localStorage.getItem('listapp_room_token_' + slug))",
                        room_slug,
                    ), "Remembered token disappeared during offline cold launch"
                finally:
                    adb("shell", "cmd", "connectivity", "airplane-mode", "disable")
                    android_server.start()
                    adb("reverse", bridge, bridge)
                page.wait_for_function(
                    """async () => {
                        try { return (await fetch('/manifest.json', {cache: 'no-store'})).ok; }
                        catch (_) { return false; }
                    }""",
                    timeout=20_000,
                )
                page.reload()
                assert page.evaluate(
                    "(slug) => Boolean(localStorage.getItem('listapp_room_token_' + slug))",
                    room_slug,
                ), "Remembered room token disappeared after cold launch"
                expect(page.get_by_role("button", name="Add New List")).to_be_visible()
            finally:
                browser.close()
    finally:
        adb("forward", "--remove", forward)
