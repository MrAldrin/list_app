"""Opt-in real-browser tests; never use the developer's database or credentials."""

import os
import secrets
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
from playwright.sync_api import sync_playwright

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
    def room_url(self):
        slug = self.query("SELECT slug FROM rooms WHERE name = 'Home'")[0][0]
        return f"{self.url}/room/{slug}"


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


@pytest.fixture(scope="session", params=["chromium", "firefox"])
def browser(request):
    with sync_playwright() as playwright:
        browser = getattr(playwright, request.param).launch()
        print(f"Browser: {request.param} {browser.version}")
        yield browser
        browser.close()


@pytest.fixture
def sessions(browser, tmp_path):
    """Separate cookie jars, localStorage, and NiceGUI sessions (not just tabs)."""
    contexts = []
    errors = []
    for role in ("member", "visitor"):
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        # Exercise the copy-dialog fallback, not OS-native sharing dialogs.
        context.add_init_script(
            "Object.defineProperty(navigator, 'share', {value: undefined})"
        )
        context.on("weberror", lambda error: errors.append(str(error.error)))
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        contexts.append((role, context))
    try:
        yield tuple(context.new_page() for _, context in contexts)
    finally:
        for role, context in contexts:
            for index, page in enumerate(context.pages):
                if not page.is_closed():
                    page.screenshot(path=str(tmp_path / f"{role}-{index}.png"))
            context.tracing.stop(path=str(tmp_path / f"{role}-trace.zip"))
            context.close()
        assert not errors, "Unhandled browser errors:\n" + "\n".join(errors)
