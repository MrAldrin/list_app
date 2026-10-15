"""Start the app in a subprocess for tests. Does not import Playwright.

Used by `tests/test_server_shutdown.py` and `browser_tests/conftest.py`. The
test database and password are never the developer's own.
"""

import os
import socket
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from contextlib import closing
from http.client import HTTPException
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
START_TIMEOUT = 30.0
STOP_TIMEOUT = 10.0


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def uvicorn_command(port: int) -> list[str]:
    """Run `main.app` with uvicorn and the same graceful shutdown timeout."""
    return [
        sys.executable,
        "-u",
        "-c",
        "import uvicorn; import main; "
        f"uvicorn.run(main.app, host='127.0.0.1', port={port}, "
        "timeout_graceful_shutdown=main.SHUTDOWN_TIMEOUT_SECONDS)",
    ]


def main_command(port: int) -> list[str]:
    """Run the real entry point, like `uv run src/main.py --port N`."""
    return [sys.executable, "-u", str(ROOT / "src" / "main.py"), "--port", str(port)]


class AppServer:
    """One app server in a subprocess, with its database and log in `directory`."""

    password = "test-only-password"

    def __init__(
        self,
        directory: Path,
        *,
        command: Callable[[int], Sequence[str]] = uvicorn_command,
        password: str | None = None,
    ):
        self.directory = directory
        self.command = command
        if password is not None:
            self.password = password
        self.database = directory / "app-test.db"
        self.log_path = directory / "server.log"
        self.process: subprocess.Popen | None = None
        self.log_file = None
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.env = {
            **os.environ,
            "DB_PATH": str(self.database),
            "APP_PASSWORD": self.password,
            "APP_RELOAD": "false",
            "PYTHON_DOTENV_DISABLED": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }

    def start(self) -> None:
        """Start the server and wait until `/manifest.json` answers.

        On early exit or timeout, stop the process and raise with the log.
        """
        self.log_file = self.log_path.open("a")
        self.process = subprocess.Popen(
            list(self.command(self.port)),
            cwd=self.directory,
            env=self.env,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
        )
        if self._wait_until_ready():
            return
        self.stop()
        raise RuntimeError(f"Test app failed to start:\n{self._log()}")

    def _wait_until_ready(self) -> bool:
        deadline = time.monotonic() + START_TIMEOUT
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                return False
            if self._answers():
                return True
            time.sleep(0.1)
        return False

    def _answers(self) -> bool:
        try:
            with urlopen(f"{self.url}/manifest.json", timeout=1) as response:
                return response.status == 200
        except (OSError, HTTPException):
            return False

    def stop(self) -> None:
        """Terminate, wait, then kill if the server does not exit."""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=STOP_TIMEOUT)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log_file:
            self.log_file.close()
            self.log_file = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def query(self, sql: str, parameters: Sequence = ()) -> list[tuple]:
        # Read-only connection: assertions cannot accidentally modify app state.
        with closing(
            sqlite3.connect(f"file:{self.database}?mode=ro", uri=True)
        ) as connection:
            return connection.execute(sql, parameters).fetchall()

    @property
    def room_slug(self) -> str:
        return self.query("SELECT slug FROM rooms WHERE name = 'Home'")[0][0]

    @property
    def room_url(self) -> str:
        return f"{self.url}/room/{self.room_slug}"

    def _log(self) -> str:
        return self.log_path.read_text() if self.log_path.exists() else ""
