"""Opt-in installed Android Chrome check for the offline feature branch."""

import socket
import sqlite3
import time

from playwright.sync_api import Error, expect, sync_playwright

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


def test_installed_room_opens_saved_lists_without_network(
    android_server: TestServer,
) -> None:
    """A prepared room stays read-only after an actual server/bridge outage."""
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
    # Dismiss an optional Chrome notifications tip without accepting a prompt.
    # The shared helper still fails on Chrome's first-run terms/privacy screen.
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
    tap_label("Add to Home screen")
    tap_label("Install")
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
            browser = playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{debug_port}"
            )
            try:
                pages = [
                    page
                    for context in browser.contexts
                    for page in context.pages
                    if page.url == url
                    and page.evaluate(
                        "matchMedia('(display-mode: standalone)').matches"
                    )
                ]
                assert len(pages) == 1, "Expected the installed room, not a browser tab"
                page = pages[0]
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
                # Removing ADB reverse alone leaves existing sockets alive; stop
                # this disposable server as well as disabling the emulator radio.
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
                    adb("shell", "input", "keyevent", "KEYCODE_HOME")
                    launch_installed_webapp(url)
                    # Chrome can replace the CDP target when the icon opens.
                    # Select the standalone activity, never the original tab.
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        pages = []
                        for context in browser.contexts:
                            for candidate in context.pages:
                                try:
                                    if candidate.url == url and candidate.evaluate(
                                        "matchMedia('(display-mode: standalone)').matches"
                                    ):
                                        pages.append(candidate)
                                except Error:
                                    continue  # Target replaced during launch.
                        if pages:
                            page = pages[-1]
                            break
                        time.sleep(0.5)
                    else:
                        raise AssertionError("Installed room did not reopen offline")
                    if not page.get_by_text("Offline · read only", exact=True).count():
                        page.reload(timeout=20_000)
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
                    assert page.locator(".items li.done").count() == 1
                    assert page.locator("input, button").count() == 0
                finally:
                    adb("shell", "cmd", "connectivity", "airplane-mode", "disable")
                    android_server.start()
                    adb("reverse", bridge, bridge)
                page.reload()
                expect(page.get_by_role("button", name="Add New List")).to_be_visible()
            finally:
                browser.close()
    finally:
        adb("forward", "--remove", forward)
