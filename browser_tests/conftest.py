"""Opt-in real-browser tests; never use the developer's database or credentials."""

import fcntl
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright
from server_launcher import AppServer

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "browser-test-room-password"


class TestServer(AppServer):
    """The app server for browser tests, with the browser test password."""

    __test__ = False
    password = PASSWORD


@pytest.fixture
def server(tmp_path):
    server = TestServer(tmp_path)
    try:
        server.start()
        yield server
    finally:
        server.stop()
        log = server.log_path.read_text() if server.log_path.exists() else ""
        assert "Traceback (most recent call last)" not in log, log


@pytest.fixture(scope="session", params=["chromium", "firefox", "webkit"])
def browser(request):
    with sync_playwright() as playwright:
        browser = getattr(playwright, request.param).launch()
        print(f"Browser: {request.param} {browser.version}")
        yield browser
        browser.close()


API_PREFIX = "/api/v1/"
API_QUIET_SECONDS = 0.3


def track_api_requests(page: Page) -> None:
    """Remember which API requests of the page have not answered yet.

    A live stream counts as answered when its response starts.
    """
    pending: set = set()
    page.api_pending = pending
    page.api_last_activity = time.monotonic()

    def touch():
        page.api_last_activity = time.monotonic()

    def started(request):
        if API_PREFIX in request.url:
            pending.add(request)
            touch()

    def ended(request):
        if request in pending:
            pending.discard(request)
            touch()

    page.on("request", started)
    page.on("response", lambda response: ended(response.request))
    page.on("requestfinished", ended)
    page.on("requestfailed", ended)


def wait_for_api_idle(page: Page, timeout_ms: int = 5_000) -> None:
    """Wait until the page has sent no API request for a short while.

    The room reloads and reopens its live stream after route changes. WebKit
    reports requests that a navigation or a closing page cancels as page
    errors, so tests wait before they leave a page.
    """
    if not hasattr(page, "api_pending"):
        return
    waited = 0
    while waited < timeout_ms and not page.is_closed():
        quiet = time.monotonic() - page.api_last_activity >= API_QUIET_SECONDS
        if quiet and not page.api_pending:
            return
        page.wait_for_timeout(25)
        waited += 25


# WebKit reports a request that a reload cancels as a page error, e.g.
# "/api/v1/rooms/<slug>/session due to access control checks."
RELOAD_CANCEL_ERROR = "due to access control checks"


class BrowserSessions:
    """Separate browser contexts with traces, screenshots and error checks."""

    def __init__(self, browser, directory: Path):
        self.browser = browser
        self.directory = directory
        self.contexts = []
        self.errors = []

    def new_page(self, role: str, **options) -> Page:
        """Open a page in a new context: its own cookies, storage and session."""
        context = self.browser.new_context(**options)
        self.contexts.append((role, context))
        # Exercise the copy-dialog fallback, not OS-native sharing dialogs.
        context.add_init_script(
            "Object.defineProperty(navigator, 'share', {value: undefined})"
        )
        context.on("weberror", self.record_error)
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        track_api_requests(page)
        return page

    def record_error(self, error) -> None:
        """Keep a page error, except a reload cancel that the page expects."""
        message = str(error.error)
        page = error.page
        if (
            page is not None
            and getattr(page, "expects_reload_cancel", False)
            and RELOAD_CANCEL_ERROR in message
        ):
            return
        self.errors.append(message)

    def close(self):
        cleanup_errors = []
        for role, context in self.contexts:
            try:
                for index, page in enumerate(context.pages):
                    if not page.is_closed():
                        try:
                            wait_for_api_idle(page)
                            page.screenshot(
                                path=str(self.directory / f"{role}-{index}.png")
                            )
                        except Exception as exc:  # noqa: BLE001 - keep cleaning up
                            cleanup_errors.append(exc)
                try:
                    context.tracing.stop(path=str(self.directory / f"{role}-trace.zip"))
                except Exception as exc:  # noqa: BLE001 - keep cleaning up
                    cleanup_errors.append(exc)
            finally:
                try:
                    context.close()
                except Exception as exc:  # noqa: BLE001 - report cleanup errors
                    cleanup_errors.append(exc)
        if self.errors:
            cleanup_errors.append(
                AssertionError("Unhandled browser errors:\n" + "\n".join(self.errors))
            )
        if cleanup_errors:
            raise ExceptionGroup(
                "Browser diagnostics and cleanup failed", cleanup_errors
            )


# Svelte frontend ------------------------------------------------------------

FRONTEND = ROOT / "frontend"
BUILD_INDEX = FRONTEND / "build" / "index.html"
BUILD_INPUTS = (
    "src",
    "static",
    "package.json",
    "package-lock.json",
    "vite.config.ts",
    "tsconfig.json",
)


def _newest_build_input() -> float:
    newest = 0.0
    for name in BUILD_INPUTS:
        path = FRONTEND / name
        files = path.rglob("*") if path.is_dir() else [path]
        for file in files:
            if file.is_file():
                newest = max(newest, file.stat().st_mtime)
    return newest


def _svelte_build_is_current() -> bool:
    return (
        BUILD_INDEX.is_file() and BUILD_INDEX.stat().st_mtime >= _newest_build_input()
    )


@pytest.fixture(scope="session")
def svelte_build(tmp_path_factory):
    """Make sure frontend/build matches frontend/src; build it if needed.

    The test servers serve the app only if the build exists when they start.
    """
    # pytest-xdist workers share the parent of their base temp folder.
    shared = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        shared = shared.parent
    with (shared / "svelte-build.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if _svelte_build_is_current():
            return
        npm = shutil.which("npm")
        if npm is None:
            pytest.fail(
                "The Svelte build is missing or older than frontend/src, and npm "
                "is not on PATH. Run `npm run build` in frontend/ first."
            )
        print("Building the Svelte frontend (npm run build)")
        result = subprocess.run(
            [npm, "run", "build"],
            cwd=FRONTEND,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not BUILD_INDEX.is_file():
            pytest.fail(
                "`npm run build` failed in frontend/:\n" + result.stdout + result.stderr
            )


@pytest.fixture
def svelte_server(svelte_build, server):
    """The test server with the Svelte app at /."""
    return server


@pytest.fixture
def open_session(browser, tmp_path):
    """Open pages in new browser contexts: `open_session(role, **options)`."""
    browser_sessions = BrowserSessions(browser, tmp_path)
    try:
        yield browser_sessions.new_page
    finally:
        browser_sessions.close()
