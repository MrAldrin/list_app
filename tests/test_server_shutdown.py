"""Stopping the real server is quick, also with an open live update stream.

Uvicorn waits for open responses before it stops, and the events stream never
ends by itself. `main.py` passes `timeout_graceful_shutdown` to `uvicorn.run()`,
so uvicorn cancels the stream after a short wait. This test starts `src/main.py`
like `uv run src/main.py` does, with a test database.
"""

import signal
import time
from collections.abc import Iterator
from pathlib import Path

import httpx2 as httpx
import pytest
from server_launcher import AppServer, main_command

from server import SHUTDOWN_TIMEOUT_SECONDS

PASSWORD = "shutdown-test-password"


@pytest.fixture
def server(tmp_path: Path) -> Iterator[AppServer]:
    server = AppServer(tmp_path, command=main_command, password=PASSWORD)
    try:
        server.start()
        yield server
    finally:
        server.stop()


def test_stopping_the_server_with_an_open_stream_is_quick(server: AppServer):
    slug = server.room_slug
    url = server.url
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
            server.process.send_signal(signal.SIGTERM)
            # Without the timeout, uvicorn waits for the stream forever.
            server.process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS + 5)
            elapsed = time.monotonic() - started

    assert elapsed < SHUTDOWN_TIMEOUT_SECONDS + 3
