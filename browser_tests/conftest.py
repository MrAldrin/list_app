"""Opt-in real-browser tests; never use the developer's database or credentials."""

import fcntl
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "browser-test-room-password"


class TestServer:
    __test__ = False
    password = PASSWORD

    def __init__(self, directory: Path):
        self.directory = directory
        self.database = directory / "browser-test.db"
        self.log_path = directory / "server.log"
        self.process = None
        self.log_file = None
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.env = {
            **{
                key: value
                for key, value in os.environ.items()
                if not key.startswith("NICEGUI_")
            },
            "DB_PATH": str(self.database),
            "APP_PASSWORD": PASSWORD,
            "NICEGUI_STORAGE_SECRET": secrets.token_urlsafe(32),
            "NICEGUI_STORAGE_PATH": str(directory / "nicegui"),
            "APP_RELOAD": "false",
            "PYTHON_DOTENV_DISABLED": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }
        # The child is a normal server, not NiceGUI's in-process pytest harness.
        self.env.pop("PYTEST_CURRENT_TEST", None)

    def start(self):
        self.log_file = self.log_path.open("a")
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                "import os; import main; "
                "main.ui.run(host='127.0.0.1', port=" + str(self.port) + ", "
                "reload=False, show=False, "
                "storage_secret=os.environ['NICEGUI_STORAGE_SECRET'])",
            ],
            cwd=self.directory,
            env=self.env,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            try:
                with urlopen(f"{self.url}/manifest.json", timeout=1) as response:
                    if response.status == 200:
                        return
            except (URLError, TimeoutError):
                time.sleep(0.1)
        raise RuntimeError(f"Test app failed to start:\n{self.log_path.read_text()}")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log_file:
            self.log_file.close()

    def restart(self):
        self.stop()
        self.start()

    def query(self, sql, parameters=()):
        # Read-only connection: assertions cannot accidentally modify app state.
        with closing(
            sqlite3.connect(f"file:{self.database}?mode=ro", uri=True)
        ) as connection:
            return connection.execute(sql, parameters).fetchall()

    @property
    def room_slug(self):
        return self.query("SELECT slug FROM rooms WHERE name = 'Home'")[0][0]

    @property
    def room_url(self):
        return f"{self.url}/room/{self.room_slug}"


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
        context.on("weberror", lambda error: self.errors.append(str(error.error)))
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        return context.new_page()

    def close(self):
        cleanup_errors = []
        for role, context in self.contexts:
            try:
                for index, page in enumerate(context.pages):
                    if not page.is_closed():
                        try:
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


@pytest.fixture
def sessions(browser, tmp_path):
    """Separate cookie jars, localStorage, and NiceGUI sessions (not just tabs)."""
    browser_sessions = BrowserSessions(browser, tmp_path)
    try:
        yield tuple(
            browser_sessions.new_page(role, viewport={"width": 1280, "height": 900})
            for role in ("member", "visitor")
        )
    finally:
        browser_sessions.close()


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

    The test servers serve /app/ only if the build exists when they start.
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
    """The test server with the Svelte app at /app/."""
    return server


@pytest.fixture
def open_session(browser, tmp_path):
    """Open pages in new browser contexts: `open_session(role, **options)`."""
    browser_sessions = BrowserSessions(browser, tmp_path)
    try:
        yield browser_sessions.new_page
    finally:
        browser_sessions.close()
