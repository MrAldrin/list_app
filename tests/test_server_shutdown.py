"""Stopping the real server is quick, also with an open live update stream.

Uvicorn waits for open responses before it stops, and the events stream never
ends by itself. `main.py` passes `timeout_graceful_shutdown` to `ui.run()`, so
uvicorn cancels the stream after a short wait. This test starts `src/main.py`
like `uv run src/main.py` does, with a test database.
"""

import os
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import httpx
import pytest

import main

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "shutdown-test-password"
START_TIMEOUT = 30.0


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def server(tmp_path: Path) -> Iterator[tuple[subprocess.Popen, str, Path]]:
    port = free_port()
    database = tmp_path / "shutdown-test.db"
    env = {
        **{
            key: value
            for key, value in os.environ.items()
            if not key.startswith("NICEGUI_")
        },
        "DB_PATH": str(database),
        "APP_PASSWORD": PASSWORD,
        "NICEGUI_STORAGE_SECRET": secrets.token_urlsafe(32),
        "NICEGUI_STORAGE_PATH": str(tmp_path / "nicegui"),
        "APP_RELOAD": "false",
        "PYTHON_DOTENV_DISABLED": "1",
        # NiceGUI opens a browser by default; `true` does nothing.
        "BROWSER": "true",
    }
    env.pop("PYTEST_CURRENT_TEST", None)
    log_path = tmp_path / "server.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "src" / "main.py"), "--port", str(port)],
            cwd=tmp_path,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        url = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + START_TIMEOUT
            while True:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f"Server did not start:\n{log_path.read_text()}")
                try:
                    if httpx.get(f"{url}/manifest.json", timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.1)
            yield process, url, database
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def room_slug(database: Path) -> str:
    with closing(sqlite3.connect(f"file:{database}?mode=ro", uri=True)) as connection:
        return connection.execute(
            "SELECT slug FROM rooms WHERE name = 'Home'"
        ).fetchone()[0]


def test_stopping_the_server_with_an_open_stream_is_quick(server):
    process, url, database = server
    slug = room_slug(database)
    with httpx.Client(base_url=url, headers={"Origin": url}, timeout=5) as client:
        login = client.post(
            f"/api/v1/rooms/{slug}/session", json={"password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        # The room cookies are Secure, so the client keeps them off plain HTTP.
        cookies = "; ".join(f"{name}={value}" for name, value in login.cookies.items())
        with client.stream(
            "GET", f"/api/v1/rooms/{slug}/events", headers={"Cookie": cookies}
        ) as stream:
            assert stream.status_code == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            lines = stream.iter_lines()
            assert next(lines).startswith("event: seq")

            started = time.monotonic()
            process.send_signal(signal.SIGTERM)
            # Without the timeout, uvicorn waits for the stream forever.
            process.wait(timeout=main.SHUTDOWN_TIMEOUT_SECONDS + 5)
            elapsed = time.monotonic() - started

    assert elapsed < main.SHUTDOWN_TIMEOUT_SECONDS + 3
