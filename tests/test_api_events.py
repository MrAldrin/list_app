"""Live updates: GET /api/v1/rooms/{slug}/events (Server-Sent Events).

TestClient and httpx's ASGITransport wait for the whole response, so an
endless stream would hang them. These tests drive the ASGI app directly with
a small fake connection, and every wait has a timeout.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from api_helpers import HTTPS, assert_error, client_for, default_list, home, new_id
from api_helpers import op as api_op
from starlette.testclient import TestClient

import database_crud as crud
import live_updates
import main
from api import events
from room_cookies import token_cookie_name

TIMEOUT = 5.0
QUIET = 0.3  # How long "nothing arrives" is checked.


class SseConnection:
    """One open events request, as a browser connection would see it."""

    def __init__(self, slug: str, token: str | None) -> None:
        path = f"/api/v1/rooms/{slug}/events"
        headers = [(b"host", b"testserver")]
        if token is not None:
            cookie = f"{token_cookie_name(slug)}={token}"
            headers.append((b"cookie", cookie.encode()))
        self.scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "root_path": "",
            "query_string": b"",
            "headers": headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 443),
        }
        self.messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.disconnected = asyncio.Event()
        self._request_sent = False
        self.status: int | None = None
        self.headers: dict[str, str] = {}
        self._buffer = ""
        self.closed = False

    async def _receive(self) -> dict[str, Any]:
        if not self._request_sent:
            self._request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await self.disconnected.wait()
        return {"type": "http.disconnect"}

    async def _send(self, message: dict[str, Any]) -> None:
        await self.messages.put(message)

    async def open(self) -> None:
        self.task = asyncio.create_task(main.app(self.scope, self._receive, self._send))
        start = await asyncio.wait_for(self.messages.get(), TIMEOUT)
        assert start["type"] == "http.response.start"
        self.status = start["status"]
        self.headers = {
            name.decode().lower(): value.decode() for name, value in start["headers"]
        }

    async def body(self) -> bytes:
        """The whole body of a non-streamed (error) response."""
        data = b""
        while True:
            message = await asyncio.wait_for(self.messages.get(), TIMEOUT)
            data += message.get("body", b"")
            if not message.get("more_body", False):
                await asyncio.wait_for(self.task, TIMEOUT)
                return data

    async def next_block(self, timeout: float = TIMEOUT) -> str | None:
        """The next SSE block (event or comment); None when the stream ended."""
        while "\n\n" not in self._buffer:
            if self.closed:
                return None
            message = await asyncio.wait_for(self.messages.get(), timeout)
            self._buffer += message.get("body", b"").decode()
            if not message.get("more_body", False):
                self.closed = True
        block, self._buffer = self._buffer.split("\n\n", 1)
        return block

    async def next_event(self, timeout: float = TIMEOUT) -> tuple[str, str]:
        block = await self.next_block(timeout)
        assert block is not None, "stream ended"
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        return fields["event"], fields["data"]

    async def assert_quiet(self) -> None:
        with pytest.raises(TimeoutError):
            await self.next_block(timeout=QUIET)

    async def ended(self) -> bool:
        """True if the app finished the response by itself."""
        await asyncio.wait_for(self.task, TIMEOUT)
        while not self.messages.empty():
            message = self.messages.get_nowait()
            self._buffer += message.get("body", b"").decode()
            if not message.get("more_body", False):
                self.closed = True
        return self.closed

    async def close(self) -> None:
        """The client goes away; the app must stop the stream promptly."""
        self.disconnected.set()
        await asyncio.wait_for(self.task, TIMEOUT)


def run(test: Callable[[], Awaitable[None]]) -> None:
    asyncio.run(asyncio.wait_for(test(), 4 * TIMEOUT))


def token_for(slug: str) -> str:
    issued = crud.authenticate_room_and_issue_token(slug, "pw")
    assert issued is not None
    return issued[1]


def room_seq(room_id: int) -> int:
    return crud.db.execute(
        "SELECT change_seq FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]


async def api_write(client: TestClient, slug: str, body: dict[str, Any]) -> dict:
    # In a worker thread, like a real request: the stream keeps running.
    return await asyncio.to_thread(api_op, client, slug, {"op_id": new_id(), **body})


@pytest.fixture
def room() -> tuple[int, str]:
    return home()


@pytest.fixture(autouse=True)
def no_leftover_streams():
    yield
    assert not live_updates._subscriptions, "a stream did not unsubscribe"


def test_connect_sends_the_current_seq_with_stream_headers(room):
    room_id, slug = room

    async def test() -> None:
        stream = SseConnection(slug, token_for(slug))
        await stream.open()
        assert stream.status == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert stream.headers["cache-control"] == "no-store"
        assert stream.headers["x-accel-buffering"] == "no"
        assert await stream.next_event() == ("seq", f'{{"seq": {room_seq(room_id)}}}')
        await stream.assert_quiet()
        await stream.close()

    run(test)


def test_no_access_is_a_401_json_error(room):
    _, slug = room
    client = TestClient(main.app, base_url=HTTPS, raise_server_exceptions=False)
    assert_error(client.get(f"/api/v1/rooms/{slug}/events"), 401, "not_authenticated")
    client.cookies.set(token_cookie_name(slug), "not-a-token")
    assert_error(client.get(f"/api/v1/rooms/{slug}/events"), 401, "not_authenticated")
    assert_error(client.get("/api/v1/rooms/nope/events"), 401, "not_authenticated")


def test_no_access_through_the_stream_path_is_json_too(room):
    _, slug = room

    async def test() -> None:
        stream = SseConnection(slug, None)
        await stream.open()
        assert stream.status == 401
        assert stream.headers["content-type"] == "application/json"
        assert b'"not_authenticated"' in await stream.body()

    run(test)


def test_an_api_write_sends_the_new_seq(room):
    _, slug = room
    client = client_for(slug)

    async def test() -> None:
        stream = SseConnection(slug, token_for(slug))
        await stream.open()
        await stream.next_event()
        response = await api_write(client, slug, {"type": "list.create", "name": "A"})
        assert await stream.next_event() == ("seq", f'{{"seq": {response["seq"]}}}')
        await stream.assert_quiet()
        await stream.close()

    run(test)


def test_a_write_outside_the_ops_endpoint_sends_the_new_seq(room):
    room_id, slug = room
    list_id, _ = default_list()

    async def test() -> None:
        stream = SseConnection(slug, token_for(slug))
        await stream.open()
        await stream.next_event()
        # A write that does not go through the ops endpoint, then the wake.
        crud.add_item_with_state("milk", list_id, False, [])
        live_updates.wake_streams(room_id)
        assert await stream.next_event() == ("seq", f'{{"seq": {room_seq(room_id)}}}')
        await stream.assert_quiet()
        await stream.close()

    run(test)


def test_writes_in_another_room_send_nothing(room):
    _, slug = room
    other_id, other_slug = crud.create_room("Other", "pw")
    other_client = client_for(other_slug)

    async def test() -> None:
        stream = SseConnection(slug, token_for(slug))
        await stream.open()
        await stream.next_event()
        await api_write(other_client, other_slug, {"type": "list.create", "name": "B"})
        await stream.assert_quiet()
        # A wake for every stream; this one sees no change in its room.
        crud.create_list("C", other_id)
        live_updates.wake_streams()
        await stream.assert_quiet()
        await stream.close()

    run(test)


def test_a_wake_without_a_change_sends_nothing(room):
    _, slug = room

    async def test() -> None:
        stream = SseConnection(slug, token_for(slug))
        await stream.open()
        await stream.next_event()
        live_updates.wake_streams()
        await stream.assert_quiet()
        await stream.close()

    run(test)


def test_revoked_access_sends_revoked_and_closes(room):
    _, slug = room
    token = token_for(slug)

    async def test() -> None:
        stream = SseConnection(slug, token)
        await stream.open()
        await stream.next_event()
        crud.revoke_room_access_token(slug, token)
        live_updates.wake_streams()
        assert await stream.next_event() == ("revoked", "{}")
        assert await stream.ended()
        assert await stream.next_block() is None

    run(test)


def test_a_password_change_is_noticed_at_the_keep_alive(room, monkeypatch):
    room_id, slug = room
    monkeypatch.setattr(events, "KEEPALIVE_SECONDS", 0.2)

    async def test() -> None:
        stream = SseConnection(slug, token_for(slug))
        await stream.open()
        await stream.next_event()
        # No wake at all: the keep-alive check still finds it.
        assert crud.update_room_password(room_id, "new", expected_slug=slug)
        assert await stream.next_event() == ("revoked", "{}")
        assert await stream.ended()

    run(test)


def test_keep_alive_comment(room, monkeypatch):
    _, slug = room
    monkeypatch.setattr(events, "KEEPALIVE_SECONDS", 0.05)

    async def test() -> None:
        stream = SseConnection(slug, token_for(slug))
        await stream.open()
        await stream.next_event()
        assert await stream.next_block() == ": keep-alive"
        assert await stream.next_block() == ": keep-alive"
        await stream.close()

    run(test)


def test_a_change_seen_at_the_keep_alive_is_sent_as_seq(room, monkeypatch):
    room_id, slug = room
    monkeypatch.setattr(events, "KEEPALIVE_SECONDS", 0.2)

    async def test() -> None:
        stream = SseConnection(slug, token_for(slug))
        await stream.open()
        await stream.next_event()
        crud.rename_room(room_id, "Renamed")  # no wake
        assert await stream.next_event() == ("seq", f'{{"seq": {room_seq(room_id)}}}')
        await stream.close()

    run(test)


def test_client_disconnect_stops_the_stream(room):
    _, slug = room

    async def test() -> None:
        stream = SseConnection(slug, token_for(slug))
        await stream.open()
        await stream.next_event()
        assert len(live_updates._subscriptions) == 1
        await stream.close()  # times out if the stream keeps running
        assert not live_updates._subscriptions

    run(test)


def test_an_api_write_wakes_the_streams_and_tells_the_listeners_once(room, monkeypatch):
    room_id, slug = room
    client = client_for(slug)
    wakes: list[int | None] = []
    listener_calls: list[int] = []
    real_wake = live_updates.wake_streams

    def counting_wake(room_id: int | None = None) -> None:
        wakes.append(room_id)
        real_wake(room_id)

    monkeypatch.setattr(live_updates, "wake_streams", counting_wake)
    monkeypatch.setattr(live_updates, "_listeners", [listener_calls.append])

    api_op(client, slug, {"op_id": new_id(), "type": "list.create", "name": "A"})
    assert wakes == [room_id]
    assert listener_calls == [room_id]


def test_streams_of_both_clients_see_each_others_writes(room):
    _, slug = room
    first, second = client_for(slug), client_for(slug)

    async def test() -> None:
        one = SseConnection(slug, token_for(slug))
        two = SseConnection(slug, token_for(slug))
        await one.open()
        await two.open()
        await one.next_event()
        await two.next_event()
        response = await api_write(first, slug, {"type": "list.create", "name": "A"})
        expected = ("seq", f'{{"seq": {response["seq"]}}}')
        assert await one.next_event() == expected
        assert await two.next_event() == expected
        response = await api_write(second, slug, {"type": "list.create", "name": "B"})
        expected = ("seq", f'{{"seq": {response["seq"]}}}')
        assert await one.next_event() == expected
        assert await two.next_event() == expected
        await one.close()
        await two.close()

    run(test)
