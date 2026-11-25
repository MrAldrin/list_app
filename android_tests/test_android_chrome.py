"""Opt-in smoke test against a running Android emulator, never a real phone."""

import os
import re
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.request import urlopen
from xml.etree import ElementTree

import pytest
from playwright.sync_api import Browser, expect, sync_playwright

from browser_tests.conftest import TestServer, TypeScriptTestServer, make_test_server

ADB = (
    Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Android/Sdk")))
    / "platform-tools/adb"
)
WINDOW_XML = "/sdcard/listr-test-window.xml"
CHROME_MENU = "com.android.chrome:id/menu_button"
LAUNCHER = "com.google.android.apps.nexuslauncher"
LAUNCHER_WORKSPACE = f"{LAUNCHER}:id/workspace"
LAUNCHER_FIRST_PAGE = f"{LAUNCHER}:id/search_container_workspace"


def adb(*args: str, timeout: int = 30) -> str:
    result = subprocess.run(
        [str(ADB), "-e", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


@pytest.fixture
def android_server(tmp_path: Path, pytestconfig: pytest.Config) -> Iterator[TestServer]:
    if not ADB.is_file():
        pytest.fail(f"Install Android platform-tools or set ANDROID_HOME: {ADB}")
    try:
        if adb("shell", "getprop", "sys.boot_completed") != "1":
            pytest.fail(
                "Start and unlock one Android emulator before this opt-in suite"
            )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        pytest.fail(f"A booted emulator is required: {error}")

    if adb("shell", "getprop", "ro.boot.qemu.avd_name") != "listapp_api35":
        pytest.fail("Use the dedicated listapp_api35 test AVD, not another emulator")
    server = make_test_server(pytestconfig, tmp_path)
    if isinstance(server, TypeScriptTestServer):
        # Chrome sends localhost as its Origin through adb reverse. The Bun
        # adapter checks it against this setting, not the host's bind address.
        server.env["LISTR_TS_ORIGIN"] = server.url.replace("127.0.0.1", "localhost")
    server.start()
    port = f"tcp:{server.port}"
    try:
        # Android localhost is a secure browser context; reverse forwards only
        # this disposable server, not a real Railway or developer database.
        adb("reverse", port, port)
        yield server
    finally:
        # cmd shortcut can only clear an entire package. Never clear Chrome's
        # shortcuts if anything besides this test's disposable icon is pinned.
        shortcuts = adb(
            "shell",
            "cmd",
            "shortcut",
            "get-shortcuts",
            "--flags",
            "4",
            "com.android.chrome",
        )
        test_url = server.room_url.replace("127.0.0.1", "localhost")
        if shortcuts.count("ShortcutInfo {id=") == 1 and (
            f"org.chromium.chrome.browser.webapp_url={test_url}}}" in shortcuts
        ):
            adb("shell", "cmd", "shortcut", "clear-shortcuts", "com.android.chrome")
        adb("reverse", "--remove", port)
        server.stop()
        log = server.log_path.read_text() if server.log_path.exists() else ""
        assert "Traceback (most recent call last)" not in log, log


def screen_nodes() -> list[ElementTree.Element]:
    adb("shell", "uiautomator", "dump", WINDOW_XML)
    root = ElementTree.fromstring(adb("exec-out", "cat", WINDOW_XML))
    return list(root.iter("node"))


def visible_text() -> str:
    return " ".join(
        value
        for node in screen_nodes()
        for value in (node.get("text"), node.get("content-desc"))
        if value
    )


def tap_bounds(bounds: str) -> None:
    points = re.findall(r"\d+", bounds)
    if len(points) != 4:
        pytest.fail(f"Invalid Android UI bounds: {bounds}")
    left, top, right, bottom = map(int, points)
    adb("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))


def tap_control(label: str, *, timeout: int = 20, package: str | None = None) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for node in screen_nodes():
            if (
                (package is None or node.get("package") == package)
                and node.get("enabled") == "true"
                and label
                in (node.get("text"), node.get("content-desc"), node.get("resource-id"))
            ):
                tap_bounds(node.get("bounds", ""))
                return
        time.sleep(0.5)
    pytest.fail(f"Android UI did not show enabled {label}: {visible_text()}")


def installed_webapp_id(url: str) -> str:
    """Wait for the exact disposable room shortcut to be pinned."""
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        shortcuts = adb(
            "shell",
            "cmd",
            "shortcut",
            "get-shortcuts",
            "--flags",
            "4",
            "com.android.chrome",
        )
        for shortcut in shortcuts.split("ShortcutInfo {id=")[1:]:
            if f"org.chromium.chrome.browser.webapp_url={url}}}" in shortcut:
                return shortcut.split(",", 1)[0]
        time.sleep(1)
    pytest.fail(f"No installed shortcut for {url}")


def wait_for_text(text: str, timeout: int = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if text in visible_text():
            return
        time.sleep(1)
    pytest.fail(f"Android UI did not show {text}: {visible_text()}")


def active_webapp_id() -> str | None:
    activity = adb("shell", "dumpsys", "activity", "activities")
    resumed = re.search(
        r"topResumedActivity=ActivityRecord\{(\w+) u\d+ com\.android\.chrome/\S*\.WebappActivity\b",
        activity,
    )
    if resumed:
        # An older installed app can still have a task. Read the intent from
        # the same activity record that is now in the foreground.
        for record in re.split(r"(?m)^[ \t]*\* Hist\s+#\d+:[ \t]*", activity)[1:]:
            if record.startswith(f"ActivityRecord{{{resumed[1]} "):
                intent = re.search(
                    r"(?m)^[ \t]*Intent \{[^\n]*\bdat=webapp://([\w-]+)", record
                )
                return intent[1] if intent else None
    return None


def launcher_workspace() -> ElementTree.Element:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        for node in screen_nodes():
            if node.get("resource-id") == LAUNCHER_WORKSPACE:
                return node
        time.sleep(0.5)
    pytest.fail("Android home screen did not open")


def swipe_launcher(*, left: bool) -> None:
    start, end = ("950", "100") if left else ("100", "950")
    adb("shell", "input", "swipe", start, "1100", end, "1100", "350")


def launcher_pages() -> Iterator[ElementTree.Element]:
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    workspace = launcher_workspace()
    # HOME from an app can return to whichever launcher page was last open.
    for _ in range(5):
        if any(n.get("resource-id") == LAUNCHER_FIRST_PAGE for n in workspace.iter()):
            break
        swipe_launcher(left=False)
        workspace = launcher_workspace()
    else:
        pytest.fail("Could not find the first Android home screen page")

    previous = None
    for _ in range(5):
        layout = tuple(
            (n.get("text"), n.get("bounds"))
            for n in workspace.iter()
            if n.get("clickable") == "true"
        )
        if layout == previous:  # Swiping past the last page leaves it in place.
            return
        yield workspace
        previous = layout
        swipe_launcher(left=True)
        workspace = launcher_workspace()


def listr_icon_bounds(workspace: ElementTree.Element) -> Iterator[str]:
    for node in workspace.iter("node"):
        if (
            node.get("text") == node.get("content-desc") == "ListR"
            and node.get("clickable") == "true"
            and (bounds := node.get("bounds"))
        ):
            yield bounds


def listr_icon_positions() -> set[tuple[int, str]]:
    return {
        (page_index, bounds)
        for page_index, workspace in enumerate(launcher_pages())
        for bounds in listr_icon_bounds(workspace)
    }


def launch_installed_webapp(url: str, position: tuple[int, str]) -> None:
    webapp_id = installed_webapp_id(url)
    page_index, bounds = position
    for index, workspace in enumerate(launcher_pages()):
        if index == page_index:
            assert bounds in listr_icon_bounds(workspace), "The new ListR icon moved"
            tap_bounds(bounds)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if active_webapp_id() == webapp_id:
                    return
                time.sleep(0.5)
            break
    pytest.fail(f"Could not launch installed shortcut {webapp_id} for {url}")


@contextmanager
def chrome_debugging() -> Iterator[Browser]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        debug_port = sock.getsockname()[1]
    forward = f"tcp:{debug_port}"
    adb("forward", forward, "localabstract:chrome_devtools_remote")
    endpoint = f"http://127.0.0.1:{debug_port}"
    try:
        # Chrome opens the debugging socket after it starts. Wait for that
        # endpoint, not a fixed delay before testing the page.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                with urlopen(f"{endpoint}/json/version", timeout=1):
                    break
            except OSError:
                time.sleep(0.25)
        else:
            pytest.fail(
                f"Android Chrome debugging endpoint did not start: {visible_text()}"
            )
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(endpoint)
            try:
                yield browser
            finally:
                browser.close()
    finally:
        adb("forward", "--remove", forward)


def start_chrome() -> None:
    # After a cold AVD boot, Chrome can restore its tabs and lose a VIEW
    # intent sent during startup. Open Chrome before asking it to navigate.
    adb(
        "shell",
        "am",
        "start",
        "-W",
        "-a",
        "android.intent.action.MAIN",
        "-c",
        "android.intent.category.LAUNCHER",
        "com.android.chrome",
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        nodes = screen_nodes()
        if any("Welcome to Chrome" in (node.get("text") or "") for node in nodes):
            pytest.fail(
                "Complete Chrome's first-run choices yourself in the emulator "
                "before running this test; the test will not agree to terms for you."
            )
        if any(node.get("resource-id") == CHROME_MENU for node in nodes):
            return
        time.sleep(0.5)
    pytest.fail(f"Chrome's toolbar did not open: {visible_text()}")


def open_room_prompt_in_chrome(url: str) -> None:
    start_chrome()
    adb(
        "shell",
        "am",
        "start",
        "-W",
        "-a",
        "android.intent.action.VIEW",
        "-d",
        url,
        "com.android.chrome",
    )
    # UI Automator can see only “Web View” in both Chrome modes. Use CDP
    # for the document while keeping native controls under UI Automator.
    with chrome_debugging() as browser:
        # Cold Chrome can expose its debug socket before it handles the VIEW
        # intent. Wait for that navigation, without opening the page over CDP.
        session = browser.new_browser_cdp_session()
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                targets = session.send("Target.getTargets")["targetInfos"]
                if any(t["type"] == "page" and t["url"] == url for t in targets):
                    break
                time.sleep(0.25)
        finally:
            session.detach()
        pages = [
            page
            for context in browser.contexts
            for page in context.pages
            if page.url == url
        ]
        assert len(pages) == 1, f"Expected Chrome to open {url}"
        page = pages[0]
        expect(
            page.get_by_role("heading", name="Enter Room Password", exact=True)
        ).to_be_visible()
        expect(page.get_by_label("Room Password", exact=True)).to_be_visible()
        expect(page.get_by_text("Admin Login", exact=True)).to_have_count(0)
        expect(page.get_by_role("button", name="Add New List")).to_have_count(0)


def test_android_chrome_opens_disposable_room(android_server: TestServer) -> None:
    """Exercise real Android Chrome without logging in."""
    url = android_server.room_url.replace("127.0.0.1", "localhost")
    open_room_prompt_in_chrome(url)


def test_install_from_password_prompt_opens_standalone_room(
    android_server: TestServer,
) -> None:
    """Installation alone must not grant access to a private room."""
    url = android_server.room_url.replace("127.0.0.1", "localhost")
    original_icons = listr_icon_positions()
    open_room_prompt_in_chrome(url)
    tap_control(CHROME_MENU)
    tap_control("Add to Home screen")
    tap_control("Install")
    wait_for_text("Install app")
    tap_control("com.android.chrome:id/positive_button")
    # Chrome 124 can wait up to 60 seconds for a WebAPK response before it
    # offers to pin the standalone app. Do not choose Create shortcut.
    tap_control("Add to home screen", timeout=90, package=LAUNCHER)
    installed_webapp_id(url)
    current_icons = listr_icon_positions()
    new_icons = current_icons - original_icons
    assert original_icons <= current_icons and len(new_icons) == 1, (
        f"Expected one new launcher icon: {original_icons=} {current_icons=}"
    )
    [position] = new_icons
    launch_installed_webapp(url, position)
    with chrome_debugging() as browser:
        candidates = [
            page
            for context in browser.contexts
            for page in context.pages
            if page.url == url
            and page.evaluate("matchMedia('(display-mode: standalone)').matches")
        ]
        assert len(candidates) == 1, "Expected exactly one installed app page"
        page = candidates[0]
        expect(page.get_by_label("Room Password", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Add New List")).to_have_count(0)
        page.get_by_label("Room Password", exact=True).fill(android_server.password)
        page.get_by_role("button", name="Enter", exact=True).click()
        expect(page.get_by_role("button", name="Add New List")).to_be_visible()
        launch_installed_webapp(url, position)
        page.reload()
        expect(page.get_by_role("button", name="Add New List")).to_be_visible()

        # ADB's tunnel can keep existing sockets alive even after its
        # mapping is removed. Stop the disposable server as well so the
        # request really fails, then restore all three in finally.
        bridge = f"tcp:{android_server.port}"
        android_server.stop()
        try:
            adb("reverse", "--remove", bridge)
            adb("shell", "cmd", "connectivity", "airplane-mode", "enable")
            assert (
                page.evaluate(
                    """async () => {
                  try {
                    await fetch('/manifest.json', {cache: 'no-store'});
                    return true;
                  } catch (_) { return false; }
                }"""
                )
                is False
            )
        finally:
            adb("shell", "cmd", "connectivity", "airplane-mode", "disable")
            android_server.start()
            adb("reverse", bridge, bridge)
        page.reload()
        expect(page.get_by_role("button", name="Add New List")).to_be_visible()
