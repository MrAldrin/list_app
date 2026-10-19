"""Every response forbids framing and MIME sniffing (src/security_headers.py).

The live update stream is checked too: the headers must not hold it back.
"""

import asyncio

import pytest
from starlette.testclient import TestClient
from test_api_events import SseConnection

import database_crud as crud
import main
from server import create_app

SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-security-policy": "frame-ancestors 'none'",
}


def assert_security_headers(response) -> None:
    for name, value in SECURITY_HEADERS.items():
        # Exactly one copy, even where a route also sets it (files do).
        assert response.headers.get_list(name) == [value], name


@pytest.fixture
def page_client(tmp_path) -> TestClient:
    build = tmp_path / "build"
    build.mkdir()
    (build / "index.html").write_text("<!doctype html><title>ListR</title>")
    (build / "robots.txt").write_text("User-agent: *\n")
    return TestClient(create_app(build))


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/last-room",  # JSON from the API
        "/api/v1/no-such-route",  # JSON error from the API
        "/static/manifest.json",  # a file from src/static
        "/sw.js",  # the old service worker kill switch
    ],
)
def test_server_routes_send_security_headers(path):
    assert_security_headers(TestClient(main.app).get(path))


def test_svelte_page_and_build_file_send_security_headers(page_client):
    assert_security_headers(page_client.get("/"))
    assert_security_headers(page_client.get("/room/home-ab12cd"))
    assert_security_headers(page_client.get("/robots.txt"))


def test_svelte_missing_build_file_sends_security_headers(page_client):
    assert_security_headers(page_client.get("/_app/immutable/missing.js"))


def test_live_stream_sends_security_headers_and_still_streams(room):
    _, slug, _ = room
    issued = crud.authenticate_room_and_issue_token(slug, "pw")
    assert issued is not None
    stream = SseConnection(slug, issued[1])

    async def test() -> None:
        await stream.open()
        try:
            assert stream.status == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            for name, value in SECURITY_HEADERS.items():
                assert stream.headers[name] == value
            # The first event arrives while the stream is still open.
            event, _ = await stream.next_event()
            assert event == "seq"
        finally:
            await stream.close()

    asyncio.run(asyncio.wait_for(test(), 20))
