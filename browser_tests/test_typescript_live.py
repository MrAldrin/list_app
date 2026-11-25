"""Check room and share signals against the built server and disposable SQLite."""

import json
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest
from test_typescript_room_access import (
    assert_error,
    assert_headers,
    client_for,
    storage,
)
from test_typescript_room_feed import apply, create_list, feed
from test_typescript_room_feed import typescript_only as typescript_only
from test_typescript_room_ops import copy_db, member
from test_typescript_share import share_link_path, share_path

from conftest import TestServer, TypeScriptTestServer

pytestmark = pytest.mark.own_server


@contextmanager
def events(client: httpx.Client, path: str) -> Iterator[Iterator[tuple[str, Any]]]:
    # Shorter than the heartbeat and recheck periods: a write must wake the stream.
    with client.stream("GET", f"{path}/events", timeout=3) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].split(";", 1)[0] == "text/event-stream"
        assert_headers(response)
        yield frames(response)


def frames(response: httpx.Response) -> Iterator[tuple[str, Any]]:
    event = None
    data = None
    for line in response.iter_lines():
        if line.startswith("event: "):
            event = line.removeprefix("event: ")
        elif line.startswith("data: "):
            data = json.loads(line.removeprefix("data: "))
        elif line == "" and event is not None:
            yield event, data
            event = data = None


def test_stream_signals_match_the_feed_and_check_access(
    server: TypeScriptTestServer,
) -> None:
    slug = server.room_slug
    room = f"/api/v1/rooms/{slug}"
    with member(server) as owner, client_for(server.url) as visitor:
        assert_error(visitor.get(f"{room}/events"), 401, "not_authenticated")
        assert_error(
            visitor.get("/api/v1/share/invalid/events"), 401, "share_unavailable"
        )
        created = create_list(owner, room, "Shared")
        uid = created["result"]["list_uid"]
        share = share_path(owner, room, uid)
        with (
            events(owner, room) as room_events,
            events(visitor, share) as shared_events,
        ):
            assert (
                next(room_events)
                == next(shared_events)
                == ("seq", {"seq": created["seq"]})
            )
            private = create_list(owner, room, "Private")
            assert next(room_events) == ("seq", {"seq": private["seq"]})
            added = apply(visitor, share, "item.add", list_uid=uid, name="eggs")
            after = added["seq"]
            # The private list must not have sent a separate signal in the share stream.
            assert next(shared_events) == next(room_events) == ("seq", {"seq": after})
            delta = feed(owner, room, private["seq"])
            assert not delta["full"] and delta["seq"] == after
            assert [row["name"] for row in delta["items"]] == ["eggs"]
            assert not feed(owner, room, after)["items"]

            reset = owner.post(share_link_path(room, uid), json={})
            assert reset.status_code == 200
            assert next(shared_events) == ("revoked", {})
            assert next(shared_events, None) is None
            assert_error(visitor.get(f"{share}/events"), 401, "share_unavailable")
            reset_seq = feed(owner, room, after)["seq"]
            assert reset_seq > after
            assert next(room_events) == ("seq", {"seq": reset_seq})

            # Simulate a restored cursor, then commit a room write to wake the stream.
            with storage(server) as db:
                db.execute("UPDATE rooms SET change_seq=0 WHERE slug=?", (slug,))
            restored = apply(owner, room, "room.rename", name="Restored")
            assert restored["seq"] < after
            assert next(room_events) == ("seq", {"seq": restored["seq"]})
            full = feed(owner, room, reset_seq)
            assert full["full"] and full["seq"] == restored["seq"]
            assert full["room"]["name"] == "Restored"

            assert visitor.post(
                "/api/v1/admin/session", json={"password": server.password}
            ).is_success
            reset_room = visitor.post(
                f"/api/v1/admin/rooms/{slug}/password",
                json={"new_password": "new live test password"},
            )
            assert reset_room.status_code == 200
            assert next(room_events) == ("revoked", {})
            assert next(room_events, None) is None
            assert_error(owner.get(f"{room}/events"), 401, "not_authenticated")


def test_stream_slots_are_shared_and_returned_after_disconnect(
    server: TypeScriptTestServer,
) -> None:
    room = f"/api/v1/rooms/{server.room_slug}"
    with (
        member(server) as owner,
        client_for(server.url) as visitor,
        ExitStack() as open_streams,
    ):
        created = create_list(owner, room)
        share = share_path(owner, room, created["result"]["list_uid"])
        # Fill all slots, split across both routes. Keep the first connection
        # separate so closing it tests cancellation instead of revocation.
        first = open_streams.enter_context(ExitStack())
        readers = [first.enter_context(events(owner, room))]
        for index in range(99):
            args = (owner, room) if index % 2 else (visitor, share)
            readers.append(open_streams.enter_context(events(*args)))
        for reader in readers:
            assert next(reader) == ("seq", {"seq": created["seq"]})
        for client, path in ((owner, room), (visitor, share)):
            with client.stream("GET", f"{path}/events", timeout=3) as response:
                assert response.status_code == 503
                response.read()
                assert_error(response, 503, "unavailable")
        first.close()
        deadline = time.monotonic() + 3
        while True:
            with visitor.stream("GET", f"{share}/events", timeout=3) as response:
                if response.status_code == 200:
                    assert next(frames(response)) == ("seq", {"seq": created["seq"]})
                    break
                response.read()
                assert_error(response, 503, "unavailable")
            assert time.monotonic() < deadline, "closed stream did not return its slot"
            time.sleep(0.02)


def test_sync_signals_on_the_same_existing_data(tmp_path: Path) -> None:
    """Compare two signals and one delta per scope, not the whole servers."""
    for sub in ("python", "bun"):
        (tmp_path / sub).mkdir()
    reference = TestServer(tmp_path / "python")
    bun = TypeScriptTestServer(tmp_path / "bun")
    try:
        reference.start()
        room = f"/api/v1/rooms/{reference.room_slug}"
        with member(reference) as owner:
            created = create_list(owner, room)
            uid = created["result"]["list_uid"]
            share = share_path(owner, room, uid)
        copy_db(reference, bun)
        bun.start()

        def observe(server: TestServer) -> object:
            with (
                member(server) as writer,
                client_for(server.url) as reader,
                events(writer, room) as room_events,
                events(reader, share) as share_events,
            ):
                initial = next(room_events), next(share_events)
                assert initial == (("seq", {"seq": created["seq"]}),) * 2
                changed = apply(
                    writer,
                    room,
                    "list.rename",
                    list_uid=uid,
                    name="Market",
                    base_seq=created["seq"],
                )
                signals = next(room_events), next(share_events)
                assert signals == (("seq", {"seq": changed["seq"]}),) * 2
                room_delta = feed(writer, room, created["seq"])
                share_view = feed(reader, share, created["seq"])
                assert not room_delta["full"] and share_view["full"]
                assert (
                    room_delta["lists"][0]["name"]
                    == share_view["lists"][0]["name"]
                    == "Market"
                )
                return initial, signals, room_delta, share_view

        assert observe(bun) == observe(reference)
    finally:
        bun.stop()
        reference.stop()
