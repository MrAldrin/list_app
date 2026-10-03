"""List write ops and the op_id helper (docs/api.md, "Writing: operations")."""

import asyncio
import sqlite3
import threading
import uuid
from typing import Any

import pytest
from starlette.testclient import TestClient

import api.ops
import database_crud as crud
import live_updates
import main
from database_setup import db

HTTPS = "https://testserver"


def home() -> tuple[int, str]:
    room_id, slug = db.execute(
        "SELECT id, slug FROM rooms WHERE name = 'Home'"
    ).fetchone()
    return room_id, slug


def client_for(slug: str | None = None, password: str = "pw") -> TestClient:
    client = TestClient(
        main.app,
        base_url=HTTPS,
        headers={"Origin": HTTPS},
        raise_server_exceptions=False,
    )
    if slug is not None:
        response = client.post(
            f"/api/v1/rooms/{slug}/session", json={"password": password}
        )
        assert response.status_code == 200
    return client


def new_id() -> str:
    return str(uuid.uuid4())


def send(client: TestClient, slug: str, body: dict[str, Any]):
    return client.post(f"/api/v1/rooms/{slug}/ops", json=body)


def op(client: TestClient, slug: str, body: dict[str, Any]) -> dict[str, Any]:
    response = send(client, slug, body)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def feed_seq(client: TestClient, slug: str) -> int:
    return client.get(f"/api/v1/rooms/{slug}/changes?since=0").json()["seq"]


def list_row(list_uid: str) -> tuple | None:
    return db.execute(
        "SELECT id, name, slug, room_id FROM lists WHERE uid = ?", (list_uid,)
    ).fetchone()


def default_list_uid() -> str:
    return db.execute("SELECT uid FROM lists WHERE name = 'default'").fetchone()[0]


def processed_ops_count() -> int:
    return db.execute("SELECT COUNT(*) FROM processed_ops").fetchone()[0]


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.headers["cache-control"] == "no-store"


@pytest.fixture
def room() -> tuple[int, str, TestClient]:
    room_id, slug = home()
    return room_id, slug, client_for(slug)


@pytest.fixture
def notified(monkeypatch) -> list[int]:
    """Room IDs passed to live-update listeners (main's listener is replaced)."""
    calls: list[int] = []
    monkeypatch.setattr(live_updates, "_listeners", [calls.append])
    return calls


# list.create


def test_create_list(room, notified):
    room_id, slug, client = room
    op_id = new_id()
    response = op(
        client, slug, {"op_id": op_id, "type": "list.create", "name": " Shop "}
    )
    list_uid = response["result"]["list_uid"]
    row = list_row(list_uid)
    assert row is not None
    assert response == {
        "op_id": op_id,
        "status": "applied",
        "result": {"list_uid": list_uid, "slug": row[2], "created": True},
        "seq": crud.get_room_seq_locked(room_id),
    }
    assert row[1] == "Shop" and row[3] == room_id
    assert response["seq"] == feed_seq(client, slug)
    assert notified == [room_id]


def test_create_list_with_client_uid(room):
    _, slug, client = room
    client_uid = new_id()
    response = op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "list.create",
            "name": "Shop",
            "uid": client_uid.upper(),
        },
    )
    assert response["result"]["list_uid"] == client_uid
    assert list_row(client_uid)[1] == "Shop"


def test_create_existing_name_returns_that_list(room, notified):
    room_id, slug, client = room
    seq = crud.get_room_seq_locked(room_id)
    client_uid = new_id()
    response = op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "list.create",
            "name": "DEFAULT",
            "uid": client_uid,
        },
    )
    assert response["status"] == "applied"
    assert response["result"]["list_uid"] == default_list_uid()
    assert response["result"]["created"] is False
    assert response["seq"] == seq
    assert list_row(client_uid) is None
    assert db.execute("SELECT COUNT(*) FROM lists").fetchone()[0] == 1


def _used_by_list() -> str:
    return default_list_uid()


def _used_by_item() -> str:
    list_id = db.execute("SELECT id FROM lists").fetchone()[0]
    crud.add_item("milk", list_id)
    return db.execute("SELECT uid FROM items").fetchone()[0]


def _used_by_deleted_list() -> str:
    room_id, _ = home()
    list_id, _ = crud.create_list("Gone", room_id)
    gone_uid = db.execute("SELECT uid FROM lists WHERE id = ?", (list_id,)).fetchone()[
        0
    ]
    crud.delete_list(list_id)
    return gone_uid


def _used_in_other_room() -> str:
    other_id, _ = crud.create_room("Other", "other-pw")
    list_id, _ = crud.create_list("Secret", other_id)
    return db.execute("SELECT uid FROM lists WHERE id = ?", (list_id,)).fetchone()[0]


@pytest.mark.parametrize(
    "used_uid",
    [_used_by_list, _used_by_item, _used_by_deleted_list, _used_in_other_room],
)
def test_create_with_a_used_uid_is_422_and_not_stored(room, used_uid):
    room_id, slug, client = room
    taken = used_uid()
    seq = crud.get_room_seq_locked(room_id)
    op_id = new_id()
    body = {"op_id": op_id, "type": "list.create", "name": "New", "uid": taken}
    assert_error(send(client, slug, body), 422, "invalid_request")
    assert processed_ops_count() == 0
    assert crud.get_room_seq_locked(room_id) == seq
    # HTTP errors are not stored: the same op_id works once the body is fixed.
    body["uid"] = new_id()
    assert op(client, slug, body)["status"] == "applied"


def test_create_with_empty_name_is_rejected(room, notified):
    room_id, slug, client = room
    seq = crud.get_room_seq_locked(room_id)
    op_id = new_id()
    response = op(client, slug, {"op_id": op_id, "type": "list.create", "name": "  "})
    assert response == {
        "op_id": op_id,
        "status": "rejected",
        "code": "invalid_name",
        "message": "Name cannot be empty",
        "seq": seq,
    }
    assert processed_ops_count() == 1
    assert notified == []


# list.rename


def test_rename_list(room, notified):
    room_id, slug, client = room
    list_uid = default_list_uid()
    before = feed_seq(client, slug)
    response = op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "list.rename",
            "list_uid": list_uid,
            "name": " Groceries ",
            # base_seq is required but not used yet: the last write wins.
            "base_seq": 0,
        },
    )
    assert response["status"] == "applied"
    assert response["result"] == {}
    assert response["seq"] == before + 1 == feed_seq(client, slug)
    assert list_row(list_uid)[1] == "Groceries"
    assert notified == [room_id]


def test_rename_to_another_case_of_its_own_name(room):
    _, slug, client = room
    list_uid = default_list_uid()
    body = {
        "op_id": new_id(),
        "type": "list.rename",
        "list_uid": list_uid,
        "name": "Default",
        "base_seq": 0,
    }
    assert op(client, slug, body)["status"] == "applied"
    assert list_row(list_uid)[1] == "Default"


@pytest.mark.parametrize(
    ("name", "code", "message"),
    [
        ("  ", "invalid_name", "Name cannot be empty"),
        (" shop ", "duplicate_name", "'shop' already exists in this room"),
    ],
)
def test_rename_rejections(room, notified, name, code, message):
    room_id, slug, client = room
    crud.create_list("Shop", room_id)
    list_uid = default_list_uid()
    seq = crud.get_room_seq_locked(room_id)
    op_id = new_id()
    body = {
        "op_id": op_id,
        "type": "list.rename",
        "list_uid": list_uid,
        "name": name,
        "base_seq": 0,
    }
    response = op(client, slug, body)
    assert response == {
        "op_id": op_id,
        "status": "rejected",
        "code": code,
        "message": message,
        "seq": seq,
    }
    assert list_row(list_uid)[1] == "default"
    assert crud.get_room_seq_locked(room_id) == seq
    assert notified == []


@pytest.mark.parametrize(
    "extra",
    [{}, {"base_seq": None}, {"base_seq": -1}, {"base_seq": "3"}, {"base_seq": True}],
)
def test_rename_needs_a_base_seq(room, extra):
    _, slug, client = room
    body = {
        "op_id": new_id(),
        "type": "list.rename",
        "list_uid": default_list_uid(),
        "name": "New",
        **extra,
    }
    assert_error(send(client, slug, body), 422, "invalid_request")


# list.delete


def test_delete_list_with_items(room, notified):
    room_id, slug, client = room
    list_id = db.execute("SELECT id FROM lists").fetchone()[0]
    crud.add_item("milk", list_id)
    list_uid = default_list_uid()
    item_uid = db.execute("SELECT uid FROM items").fetchone()[0]
    before = feed_seq(client, slug)
    response = op(
        client, slug, {"op_id": new_id(), "type": "list.delete", "list_uid": list_uid}
    )
    assert response["status"] == "applied" and response["result"] == {}
    assert list_row(list_uid) is None
    assert db.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
    delta = client.get(f"/api/v1/rooms/{slug}/changes?since={before}").json()
    assert delta["seq"] == response["seq"]
    assert delta["deletions"] == [
        {"kind": "item", "uid": item_uid},
        {"kind": "list", "uid": list_uid},
    ]
    assert notified == [room_id]


@pytest.mark.parametrize("op_type", ["list.rename", "list.delete"])
def test_missing_list_is_unavailable(room, notified, op_type):
    _, slug, client = room
    body = {"op_id": new_id(), "type": op_type, "list_uid": new_id()}
    if op_type == "list.rename":
        body |= {"name": "X", "base_seq": 0}
    response = op(client, slug, body)
    assert response["status"] == "rejected"
    assert response["code"] == "list_unavailable"
    assert response["message"] == "The list is no longer available."
    assert notified == []


@pytest.mark.parametrize("op_type", ["list.rename", "list.delete"])
def test_list_in_another_room_is_unavailable(room, op_type):
    _, slug, client = room
    other_id, _ = crud.create_room("Other", "other-pw")
    other_list_id, _ = crud.create_list("Secret", other_id)
    other_uid = db.execute(
        "SELECT uid FROM lists WHERE id = ?", (other_list_id,)
    ).fetchone()[0]
    other_seq = crud.get_room_seq_locked(other_id)
    body = {"op_id": new_id(), "type": op_type, "list_uid": other_uid}
    if op_type == "list.rename":
        body |= {"name": "Hacked", "base_seq": 0}
    response = op(client, slug, body)
    assert response["code"] == "list_unavailable"
    assert list_row(other_uid)[1] == "Secret"
    assert crud.get_room_seq_locked(other_id) == other_seq


# Replays and op_id reuse


def test_replay_returns_the_stored_response_without_writing_again(room, notified):
    room_id, slug, client = room
    body = {"op_id": new_id(), "type": "list.create", "name": "Shop"}
    first = send(client, slug, body)
    seq = crud.get_room_seq_locked(room_id)
    # The world moves on; the replay still answers as the first time.
    list_uid = first.json()["result"]["list_uid"]
    crud.rename_list(list_row(list_uid)[0], "Market")
    later_seq = crud.get_room_seq_locked(room_id)
    second = send(client, slug, body)
    assert second.status_code == 200
    assert second.content == first.content
    assert second.json()["seq"] == seq
    assert crud.get_room_seq_locked(room_id) == later_seq
    assert db.execute("SELECT COUNT(*) FROM lists").fetchone()[0] == 2
    assert processed_ops_count() == 1
    assert notified == [room_id]


def test_replay_of_a_delete_does_not_become_unavailable(room):
    _, slug, client = room
    body = {"op_id": new_id(), "type": "list.delete", "list_uid": default_list_uid()}
    first = op(client, slug, body)
    assert first["status"] == "applied"
    assert op(client, slug, body) == first


def test_replay_of_a_rejection_is_the_same_rejection(room, notified):
    room_id, slug, client = room
    body = {
        "op_id": new_id(),
        "type": "list.rename",
        "list_uid": default_list_uid(),
        "name": "Shop",
        "base_seq": 0,
    }
    crud.create_list("Shop", room_id)
    first = op(client, slug, body)
    assert first["code"] == "duplicate_name"
    # Even after the cause is gone, the stored answer stays.
    crud.rename_list(
        db.execute("SELECT id FROM lists WHERE name = 'Shop'").fetchone()[0], "Market"
    )
    assert op(client, slug, body) == first
    assert list_row(default_list_uid())[1] == "default"
    assert notified == []


def test_same_op_id_with_another_body_is_409(room):
    room_id, slug, client = room
    op_id = new_id()
    op(client, slug, {"op_id": op_id, "type": "list.create", "name": "Shop"})
    seq = crud.get_room_seq_locked(room_id)
    response = send(
        client, slug, {"op_id": op_id, "type": "list.create", "name": "Other"}
    )
    assert_error(response, 409, "op_id_reused")
    assert crud.get_room_seq_locked(room_id) == seq
    assert crud.find_list_by_name("Other", room_id) is None


def test_same_op_id_in_another_room_is_409(room):
    _, slug, client = room
    _, other_slug = crud.create_room("Other", "other-pw")
    other = client_for(other_slug, "other-pw")
    body = {"op_id": new_id(), "type": "list.create", "name": "Shop"}
    op(client, slug, body)
    assert_error(send(other, other_slug, body), 409, "op_id_reused")


def test_same_body_with_spelling_variants_is_the_same_request(room):
    _, slug, client = room
    op_id = new_id()
    first = op(client, slug, {"op_id": op_id, "type": "list.create", "name": "Shop"})
    again = op(
        client,
        slug,
        {"name": "Shop", "type": "list.create", "op_id": op_id.upper(), "uid": None},
    )
    assert again == first


def test_unexpected_error_rolls_back_and_stores_nothing(room, monkeypatch, notified):
    room_id, slug, client = room
    seq = crud.get_room_seq_locked(room_id)

    def boom(list_id: int) -> str:
        raise RuntimeError("bug after the insert")

    monkeypatch.setattr(api.ops, "get_list_uid_locked", boom)
    body = {"op_id": new_id(), "type": "list.create", "name": "Shop"}
    assert_error(send(client, slug, body), 500, "internal_error")
    assert crud.find_list_by_name("Shop", room_id) is None
    assert crud.get_room_seq_locked(room_id) == seq
    assert processed_ops_count() == 0
    assert notified == []


def test_database_error_is_503_and_not_stored(room, monkeypatch):
    _, slug, client = room

    def locked(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(api.ops, "create_or_find_list_locked", locked)
    body = {"op_id": new_id(), "type": "list.create", "name": "Shop"}
    assert_error(send(client, slug, body), 503, "unavailable")
    assert processed_ops_count() == 0


# Request rules


@pytest.mark.parametrize(
    "body",
    [
        {"type": "list.create", "name": "Shop"},
        {"op_id": "not-a-uuid", "type": "list.create", "name": "Shop"},
        {"op_id": 5, "type": "list.create", "name": "Shop"},
        {"op_id": "OP", "type": "list.create", "name": "Shop"},
        {"op_id": "{op_id}", "name": "Shop"},
        {"op_id": "{op_id}", "type": "list.explode", "name": "Shop"},
        {"op_id": "{op_id}", "type": "list.create"},
        {"op_id": "{op_id}", "type": "list.create", "name": None},
        {"op_id": "{op_id}", "type": "list.create", "name": 5},
        {"op_id": "{op_id}", "type": "list.create", "name": "Shop", "uid": "nope"},
        {"op_id": "{op_id}", "type": "list.create", "name": "Shop", "extra": 1},
        {"op_id": "{op_id}", "type": "list.delete"},
        {"op_id": "{op_id}", "type": "list.delete", "list_uid": "nope"},
    ],
)
def test_bad_bodies_are_422(room, body):
    _, slug, client = room
    op_id = new_id()
    body = {k: (op_id if v == "{op_id}" else v) for k, v in body.items()}
    assert_error(send(client, slug, body), 422, "invalid_request")
    assert processed_ops_count() == 0


def test_body_must_be_a_json_object(room):
    _, slug, client = room
    assert_error(send(client, slug, ["list.create"]), 422, "invalid_request")
    response = client.post(
        f"/api/v1/rooms/{slug}/ops",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert_error(response, 400, "invalid_request")


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": HTTPS, "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_origin_ops_are_rejected(room, headers):
    room_id, slug, client = room
    seq = crud.get_room_seq_locked(room_id)
    response = client.post(
        f"/api/v1/rooms/{slug}/ops",
        json={"op_id": new_id(), "type": "list.create", "name": "Shop"},
        headers=headers,
    )
    assert_error(response, 403, "forbidden_origin")
    assert crud.get_room_seq_locked(room_id) == seq
    assert processed_ops_count() == 0


def test_ops_need_a_json_content_type(room):
    _, slug, client = room
    response = client.post(
        f"/api/v1/rooms/{slug}/ops",
        content=b'{"op_id": "x"}',
        headers={"Content-Type": "text/plain"},
    )
    assert_error(response, 415, "invalid_request")


def test_no_access_and_unknown_room_look_the_same(room):
    room_id, slug, _ = room
    _, other_slug = crud.create_room("Other", "other-pw")
    stranger = client_for()
    body = {"op_id": new_id(), "type": "list.create", "name": "Shop"}
    no_cookie = send(stranger, slug, body)
    unknown = send(stranger, "no-such-room", body)
    other_room_cookie = send(client_for(other_slug, "other-pw"), slug, body)
    for response in (no_cookie, unknown, other_room_cookie):
        assert_error(response, 401, "not_authenticated")
    assert no_cookie.content == unknown.content == other_room_cookie.content
    assert crud.find_list_by_name("Shop", room_id) is None
    assert processed_ops_count() == 0


def test_revoked_access_cannot_write(room):
    room_id, slug, client = room
    crud.update_room_password(room_id, "new-password")
    body = {"op_id": new_id(), "type": "list.create", "name": "Shop"}
    assert_error(send(client, slug, body), 401, "not_authenticated")
    assert crud.find_list_by_name("Shop", room_id) is None


# Live updates for NiceGUI


def test_nicegui_listener_is_registered():
    assert main._refresh_nicegui_pages in live_updates._listeners


def test_nicegui_refresh_runs_on_the_event_loop(monkeypatch):
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    refreshed = threading.Event()
    refresh_threads: list[threading.Thread] = []

    def fake_broadcast() -> None:
        refresh_threads.append(threading.current_thread())
        refreshed.set()

    monkeypatch.setattr(main, "refresh_open_pages", fake_broadcast)
    monkeypatch.setattr(main.core, "loop", loop)
    try:
        main._refresh_nicegui_pages(1)  # from this (non-loop) thread
        assert refreshed.wait(5)
        assert refresh_threads == [thread]
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)
        loop.close()


def test_nicegui_refresh_without_a_running_app_does_nothing(monkeypatch):
    monkeypatch.setattr(main.core, "loop", None)
    monkeypatch.setattr(
        main, "refresh_open_pages", lambda: pytest.fail("must not refresh")
    )
    main._refresh_nicegui_pages(1)


def test_api_write_refreshes_nicegui_pages(room, monkeypatch):
    _, slug, client = room
    scheduled = []

    class FakeLoop:
        def is_closed(self) -> bool:
            return False

        def call_soon_threadsafe(self, callback) -> None:
            scheduled.append(callback)

    monkeypatch.setattr(main.core, "loop", FakeLoop())
    op(client, slug, {"op_id": new_id(), "type": "list.create", "name": "Shop"})
    # Only the refresh: the API write already woke the live streams.
    assert scheduled == [main.refresh_open_pages]


def test_a_failing_listener_does_not_fail_the_write(room, monkeypatch):
    room_id, slug, client = room

    def broken(room_id: int) -> None:
        raise RuntimeError("listener bug")

    monkeypatch.setattr(live_updates, "_listeners", [broken])
    response = op(
        client, slug, {"op_id": new_id(), "type": "list.create", "name": "Shop"}
    )
    assert response["status"] == "applied"
    assert crud.find_list_by_name("Shop", room_id) is not None


# Pruning stored op results


def _store_op(room_id: int, age: str) -> str:
    op_id = new_id()
    db.execute(
        "INSERT INTO processed_ops (op_id, room_id, request_hash, response_json, "
        "created_at) VALUES (?, ?, 'h', '{}', strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?))",
        (op_id, room_id, age),
    )
    db.commit()
    return op_id


def test_prune_processed_ops_drops_entries_older_than_30_days():
    room_id, _ = home()
    old = _store_op(room_id, "-31 days")
    recent = _store_op(room_id, "-29 days")
    fresh = _store_op(room_id, "+0 days")
    assert crud.prune_processed_ops() == 1
    kept = {row[0] for row in db.execute("SELECT op_id FROM processed_ops")}
    assert kept == {recent, fresh}
    assert old not in kept


def test_prune_runs_at_startup():
    assert main._prune_processed_ops in main.app._startup_handlers


def test_startup_prune_survives_a_database_error(monkeypatch, caplog):
    def locked(*args: object) -> int:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(main, "prune_processed_ops", locked)
    main._prune_processed_ops()
    assert "Could not prune processed_ops" in caplog.text
