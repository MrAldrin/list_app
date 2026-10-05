"""Public share links in the JSON API (docs/api.md, "Share links").

The rules are NiceGUI's (docs/public-sharing.md): a share token opens one list
for viewing and editing, never the room. Only room members read and reset the
link, and a reset blocks the old token at once, also for queued edits.
"""

import asyncio
import sqlite3

import pytest
from api_helpers import (
    HTTPS,
    add_item,
    assert_error,
    changes,
    client_for,
    home,
    item_row,
    new_id,
    processed_ops_count,
    row_counts,
)
from starlette.testclient import TestClient
from test_api_events import SseConnection, run

import api.share
import database_crud as crud
import live_updates
import main
from database_setup import db


def share_token(list_id: int) -> str:
    return db.execute(
        "SELECT share_token FROM lists WHERE id = ?", (list_id,)
    ).fetchone()[0]


def public_client() -> TestClient:
    """A browser without room access: it only has the link."""
    return client_for()


def share_changes(client: TestClient, token: str, since: int = 0):
    return client.get(f"/api/v1/share/{token}/changes?since={since}")


def share_send(client: TestClient, token: str, body: dict):
    return client.post(f"/api/v1/share/{token}/ops", json=body)


def share_op(client: TestClient, token: str, body: dict) -> dict:
    response = share_send(client, token, {"op_id": new_id(), **body})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def share_link(client: TestClient, slug: str, list_uid: str):
    return client.get(f"/api/v1/rooms/{slug}/lists/{list_uid}/share-link")


def reset_link(client: TestClient, slug: str, list_uid: str, body: dict | None = None):
    return client.post(
        f"/api/v1/rooms/{slug}/lists/{list_uid}/share-link",
        json={} if body is None else body,
    )


def uid_of_list(list_id: int) -> str:
    return db.execute("SELECT uid FROM lists WHERE id = ?", (list_id,)).fetchone()[0]


@pytest.fixture
def shared():
    """A shared list in Home with one item, and another list in Home."""
    room_id, slug = home()
    list_id, _ = crud.create_list("Groceries", room_id)
    item_uid = add_item(list_id, "milk")
    other_id, _ = crud.create_list("Private", room_id)
    other_item = add_item(other_id, "secret")
    return {
        "room_id": room_id,
        "slug": slug,
        "list_id": list_id,
        "list_uid": uid_of_list(list_id),
        "item_uid": item_uid,
        "token": share_token(list_id),
        "other_id": other_id,
        "other_uid": uid_of_list(other_id),
        "other_item": other_item,
    }


@pytest.fixture
def notified(monkeypatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(live_updates, "_listeners", [calls.append])
    return calls


# Reading by token


def test_share_feed_is_a_full_snapshot_of_only_the_shared_list(shared):
    response = share_changes(public_client(), shared["token"])

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    feed = response.json()
    room_feed = changes(client_for(shared["slug"]), shared["slug"], 0)
    assert feed["seq"] == room_feed["seq"]
    assert feed["full"] is True
    assert feed["room"] is None
    assert feed["deletions"] == []
    [shared_list] = [li for li in room_feed["lists"] if li["uid"] == shared["list_uid"]]
    # The slug is room navigation; the share holder does not get it.
    assert feed["lists"] == [{**shared_list, "slug": ""}]
    assert [item["uid"] for item in feed["items"]] == [shared["item_uid"]]
    assert shared["token"] not in response.text


def test_share_feed_ignores_since_and_never_sends_deletions(shared):
    client = public_client()
    seq = share_changes(client, shared["token"]).json()["seq"]
    crud.delete_item(
        db.execute(
            "SELECT id FROM items WHERE uid = ?", (shared["other_item"],)
        ).fetchone()[0],
        shared["other_id"],
    )

    feed = share_changes(client, shared["token"], seq).json()

    assert feed["full"] is True
    assert feed["deletions"] == []
    assert [item["uid"] for item in feed["items"]] == [shared["item_uid"]]


@pytest.mark.parametrize("since", ["-1", "x", "", str(2**63)])
def test_share_feed_checks_since(shared, since):
    response = public_client().get(
        f"/api/v1/share/{shared['token']}/changes?since={since}"
    )
    assert_error(response, 422, "invalid_request")


def invalid_tokens(shared) -> list[str]:
    list_slug = db.execute(
        "SELECT slug FROM lists WHERE id = ?", (shared["list_id"],)
    ).fetchone()[0]
    return [
        shared["token"][:-1],
        shared["token"] + "x",
        "x" * 43,
        list_slug,
        shared["slug"],
    ]


def test_invalid_tokens_reveal_nothing(shared):
    client = client_for(shared["slug"])  # Room access does not help either.
    for token in invalid_tokens(shared):
        assert_error(share_changes(client, token), 401, "share_unavailable")
        response = share_send(
            client,
            token,
            {
                "op_id": new_id(),
                "type": "item.add",
                "list_uid": shared["list_uid"],
                "name": "x",
            },
        )
        assert_error(response, 401, "share_unavailable")
        assert_error(
            client.get(f"/api/v1/share/{token}/events"), 401, "share_unavailable"
        )
    assert db.execute("SELECT COUNT(*) FROM items WHERE name = 'x'").fetchone() == (0,)


def test_a_deleted_list_looks_like_a_reset_link(shared):
    crud.delete_list(shared["list_id"])
    response = share_changes(public_client(), shared["token"])
    assert_error(response, 401, "share_unavailable")
    assert (
        response.json()["error"]["message"]
        == "This list was deleted or this share link was reset."
    )


# Writing by token


def test_share_holder_edits_items_tags_and_hide_done(shared, notified):
    client = public_client()
    token, list_uid = shared["token"], shared["list_uid"]

    added = share_op(
        client, token, {"type": "item.add", "list_uid": list_uid, "name": " Bread "}
    )
    assert added["status"] == "applied"
    assert added["result"]["outcome"] == "added"
    bread = added["result"]["item_uid"]
    for body in (
        {"type": "item.set_done", "item_uid": bread, "done": True},
        {"type": "item.quantity_delta", "item_uid": bread, "delta": 2},
        {"type": "list.tag_add", "tag": "Lidl"},
        {"type": "item.toggle_tag", "item_uid": bread, "tag": "Lidl"},
        {"type": "list.visibility", "mode": "all"},
        {
            "type": "item.edit",
            "item_uid": shared["item_uid"],
            "name": "oat milk",
            "description": "cold",
            "base_seq": 0,
        },
    ):
        response = share_op(client, token, {"list_uid": list_uid, **body})
        assert response["status"] == "applied", (body, response)

    row = item_row(bread)
    assert row is not None
    assert row["completed_at"] is not None
    assert {
        key: row[key] for key in ("name", "done", "quantity", "tags", "list_id")
    } == {
        "name": "bread",
        "done": 1,
        "quantity": 3,
        "tags": '["Lidl"]',
        "list_id": shared["list_id"],
    }
    assert item_row(shared["item_uid"])["name"] == "oat milk"
    details = crud.get_list_details(shared["list_id"])
    assert details["list_tags"] == ["Lidl"]
    assert details["hide_done_mode"] == "all"
    # Every applied op tells the room's listeners (NiceGUI pages, streams).
    assert notified == [shared["room_id"]] * 7
    feed = share_changes(client, token).json()
    assert feed["seq"] == added["seq"] + 6


def test_share_holder_deletes_and_restores_an_item(shared):
    client = public_client()
    token, list_uid = shared["token"], shared["list_uid"]
    deleted = share_op(
        client,
        token,
        {"type": "item.delete", "list_uid": list_uid, "item_uid": shared["item_uid"]},
    )
    assert deleted["status"] == "applied"
    assert item_row(shared["item_uid"]) is None

    restored = share_op(
        client,
        token,
        {
            "type": "item.restore",
            "list_uid": list_uid,
            "name": "milk",
            "done": False,
            "tags": [],
            "description": "",
            "quantity": 1,
            "completed_at": None,
        },
    )
    assert restored["status"] == "applied"
    assert item_row(restored["result"]["item_uid"])["name"] == "milk"


def test_business_rules_reject_like_in_the_room(shared):
    response = share_op(
        public_client(),
        shared["token"],
        {"type": "item.add", "list_uid": shared["list_uid"], "name": "MILK"},
    )
    assert response["status"] == "rejected"
    assert response["code"] == "duplicate_active"
    assert response["message"] == "'milk' is already on the list"


def test_share_ops_reach_no_other_list(shared, notified):
    client = public_client()
    other_room_id, _ = crud.create_room("Cabin", "cabin-pw")
    cabin_list, _ = crud.create_list("Cabin list", other_room_id)
    cabin_uid = uid_of_list(cabin_list)
    before = row_counts()

    for list_uid in (shared["other_uid"], cabin_uid, new_id()):
        for body in (
            {"type": "item.add", "name": "intruder"},
            {"type": "list.tag_add", "tag": "intruder"},
            {
                "type": "item.delete",
                "item_uid": shared["other_item"],
            },
        ):
            response = share_op(client, shared["token"], {"list_uid": list_uid, **body})
            assert response["status"] == "rejected"
            assert response["code"] == "list_unavailable"

    # An item of another list, sent with the shared list's uid.
    response = share_op(
        client,
        shared["token"],
        {
            "type": "item.set_done",
            "list_uid": shared["list_uid"],
            "item_uid": shared["other_item"],
            "done": True,
        },
    )
    assert response["code"] == "item_not_found"
    assert row_counts() == before
    assert item_row(shared["other_item"])["done"] == 0
    assert crud.get_list_details(shared["other_id"])["list_tags"] == []
    assert notified == []


@pytest.mark.parametrize(
    "body",
    [
        {"type": "room.rename", "name": "Taken"},
        {"type": "list.create", "name": "New list"},
        {"type": "list.rename", "name": "Renamed", "base_seq": 0},
        {"type": "list.delete"},
    ],
)
def test_share_link_cannot_change_the_room_or_the_list_itself(shared, body):
    # As on NiceGUI's public page: no list rename, no list delete, no room.
    if body["type"].startswith("list.") and body["type"] != "list.create":
        body = {**body, "list_uid": shared["list_uid"]}
    before_ops = processed_ops_count()

    response = share_send(public_client(), shared["token"], {"op_id": new_id(), **body})

    assert_error(response, 422, "invalid_request")
    assert db.execute(
        "SELECT name FROM rooms WHERE id = ?", (shared["room_id"],)
    ).fetchone() == ("Home",)
    assert [row[0] for row in db.execute("SELECT name FROM lists ORDER BY id")] == [
        "default",
        "Groceries",
        "Private",
    ]
    assert processed_ops_count() == before_ops


def test_share_op_is_retry_safe(shared):
    client = public_client()
    body = {
        "op_id": new_id(),
        "type": "item.quantity_delta",
        "list_uid": shared["list_uid"],
        "item_uid": shared["item_uid"],
        "delta": 1,
    }
    first = share_send(client, shared["token"], body).json()
    again = share_send(client, shared["token"], body).json()

    assert again == first
    assert item_row(shared["item_uid"])["quantity"] == 2
    response = share_send(client, shared["token"], {**body, "delta": 5})
    assert_error(response, 409, "op_id_reused")


def test_share_writes_need_same_origin_and_json(shared):
    client = TestClient(main.app, base_url=HTTPS, raise_server_exceptions=False)
    body = {
        "op_id": new_id(),
        "type": "item.add",
        "list_uid": shared["list_uid"],
        "name": "cross-site",
    }
    response = client.post(f"/api/v1/share/{shared['token']}/ops", json=body)
    assert_error(response, 403, "forbidden_origin")
    response = client.post(
        f"/api/v1/share/{shared['token']}/ops",
        json=body,
        headers={"Origin": "https://evil.example"},
    )
    assert_error(response, 403, "forbidden_origin")
    response = public_client().post(
        f"/api/v1/share/{shared['token']}/ops",
        content=b"{}",
        headers={"Content-Type": "text/plain"},
    )
    assert_error(response, 415, "invalid_request")
    assert item_row(shared["item_uid"]) is not None
    assert db.execute(
        "SELECT COUNT(*) FROM items WHERE name = 'cross-site'"
    ).fetchone() == (0,)


def test_a_share_link_never_gives_room_access(shared):
    client = public_client()
    share_op(
        client,
        shared["token"],
        {"type": "item.add", "list_uid": shared["list_uid"], "name": "eggs"},
    )
    # The share endpoints set no cookies.
    assert not client.cookies
    slug = shared["slug"]
    assert_error(client.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")
    assert_error(
        client.get(f"/api/v1/rooms/{slug}/changes?since=0"), 401, "not_authenticated"
    )
    assert_error(share_link(client, slug, shared["list_uid"]), 401, "not_authenticated")
    assert_error(reset_link(client, slug, shared["list_uid"]), 401, "not_authenticated")
    # The token is not a room token either.
    client.cookies.set(f"__Host-listapp-room-{'0' * 64}", shared["token"])
    assert_error(client.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")
    assert share_token(shared["list_id"]) == shared["token"]


# Reading and resetting the link (room members)


def test_room_member_reads_the_share_link(shared):
    client = client_for(shared["slug"])
    response = share_link(client, shared["slug"], shared["list_uid"])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"token": shared["token"]}
    # Upper case uids work like in ops.
    response = share_link(client, shared["slug"], shared["list_uid"].upper())
    assert response.json() == {"token": shared["token"]}


def test_share_link_of_a_list_in_another_room_is_unavailable(shared):
    _, cabin_slug = crud.create_room("Cabin", "cabin-pw")
    cabin = client_for(cabin_slug, "cabin-pw")
    for list_uid in (shared["list_uid"], new_id(), "not-a-uuid"):
        assert_error(share_link(cabin, cabin_slug, list_uid), 404, "list_unavailable")
        assert_error(reset_link(cabin, cabin_slug, list_uid), 404, "list_unavailable")
    assert share_token(shared["list_id"]) == shared["token"]


def test_reset_gives_a_new_link_and_blocks_the_old_one(shared, notified):
    room = client_for(shared["slug"])
    public = public_client()
    before = changes(room, shared["slug"], 0)["seq"]

    response = reset_link(room, shared["slug"], shared["list_uid"])

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    new = response.json()["token"]
    assert len(new) == 43
    assert new != shared["token"]
    assert share_token(shared["list_id"]) == new
    assert notified == [shared["room_id"]]
    assert changes(room, shared["slug"], 0)["seq"] > before
    # The old link is gone at once, for reads and for writes.
    assert_error(share_changes(public, shared["token"]), 401, "share_unavailable")
    old_write = share_send(
        public,
        shared["token"],
        {
            "op_id": new_id(),
            "type": "item.add",
            "list_uid": shared["list_uid"],
            "name": "forbidden",
        },
    )
    assert_error(old_write, 401, "share_unavailable")
    # The new link works; room access stays.
    assert share_changes(public, new).status_code == 200
    share_op(
        public,
        new,
        {"type": "item.add", "list_uid": shared["list_uid"], "name": "allowed"},
    )
    assert room.get(f"/api/v1/rooms/{shared['slug']}/session").status_code == 200
    names = [row[0] for row in db.execute("SELECT name FROM items ORDER BY id")]
    assert "forbidden" not in names
    assert "allowed" in names
    # Other lists keep their links.
    assert share_changes(public, share_token(shared["other_id"])).status_code == 200


def test_reset_blocks_a_retry_of_an_op_sent_before(shared):
    public = public_client()
    body = {
        "op_id": new_id(),
        "type": "item.delete",
        "list_uid": shared["list_uid"],
        "item_uid": shared["item_uid"],
    }
    # The answer to an undo was lost; the link is reset; the retry comes.
    first = share_send(public, shared["token"], body)
    assert first.status_code == 200
    reset_link(client_for(shared["slug"]), shared["slug"], shared["list_uid"])

    assert_error(share_send(public, shared["token"], body), 401, "share_unavailable")


@pytest.mark.parametrize("credential", ["missing", "wrong-room", "revoked"])
def test_reset_needs_current_room_access(shared, credential):
    slug = shared["slug"]
    if credential == "missing":
        client = public_client()
    elif credential == "wrong-room":
        _, cabin_slug = crud.create_room("Cabin", "cabin-pw")
        client = client_for(cabin_slug, "cabin-pw")
        # Cabin's cookie is not for Home.
    else:
        client = client_for(slug)
        crud.update_room_password(shared["room_id"], "new-pw")

    assert_error(reset_link(client, slug, shared["list_uid"]), 401, "not_authenticated")
    assert_error(share_link(client, slug, shared["list_uid"]), 401, "not_authenticated")
    assert share_token(shared["list_id"]) == shared["token"]


def test_reset_rules_for_the_request(shared):
    room = client_for(shared["slug"])
    url = f"/api/v1/rooms/{shared['slug']}/lists/{shared['list_uid']}/share-link"
    assert_error(
        reset_link(room, shared["slug"], shared["list_uid"], {"x": 1}),
        422,
        "invalid_request",
    )
    assert_error(room.post(url), 415, "invalid_request")
    no_origin = TestClient(main.app, base_url=HTTPS, raise_server_exceptions=False)
    no_origin.cookies = room.cookies
    assert_error(no_origin.post(url, json={}), 403, "forbidden_origin")
    assert share_token(shared["list_id"]) == shared["token"]


def test_password_change_keeps_share_links(shared):
    # Share links are independent of room passwords (docs/public-sharing.md).
    client = client_for(shared["slug"])
    response = client.post(
        f"/api/v1/rooms/{shared['slug']}/password",
        json={"current_password": "pw", "new_password": "new-pw"},
    )
    assert response.status_code == 200
    assert share_changes(public_client(), shared["token"]).status_code == 200


def test_nicegui_reset_blocks_the_api_and_api_reset_blocks_nicegui(shared):
    _, room_token = crud.authenticate_room_and_issue_token(shared["slug"], "pw")
    list_slug = crud.get_list_details(shared["list_id"])["slug"]
    new = crud.rotate_list_share_token(
        shared["slug"], room_token, shared["list_id"], expected_slug=list_slug
    )
    public = public_client()
    assert_error(share_changes(public, shared["token"]), 401, "share_unavailable")

    newer = reset_link(client_for(shared["slug"]), shared["slug"], shared["list_uid"])
    with pytest.raises(crud.ListUnavailable):
        crud.add_item("blocked", shared["list_id"], expected_slug=f"share:{new}")
    crud.add_item(
        "allowed", shared["list_id"], expected_slug=f"share:{newer.json()['token']}"
    )


def test_a_failed_reset_changes_nothing(shared, monkeypatch, notified):
    room = client_for(shared["slug"])

    def broken(list_id: int) -> str:
        crud.db.execute(
            "UPDATE lists SET share_token = 'half' WHERE id = ?", (list_id,)
        )
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(api.share, "rotate_share_token_locked", broken)
    assert_error(
        reset_link(room, shared["slug"], shared["list_uid"]), 503, "unavailable"
    )
    assert share_token(shared["list_id"]) == shared["token"]
    assert notified == []


# Live updates by token


def share_stream(token: str) -> SseConnection:
    stream = SseConnection("unused", None)
    path = f"/api/v1/share/{token}/events"
    stream.scope["path"] = path
    stream.scope["raw_path"] = path.encode()
    return stream


def test_share_stream_sends_seq_and_revoked_after_a_reset(shared):
    room = client_for(shared["slug"])
    public = public_client()

    async def test() -> None:
        stream = share_stream(shared["token"])
        await stream.open()
        assert stream.status == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert stream.headers["cache-control"] == "no-store"
        seq = share_changes(public, shared["token"]).json()["seq"]
        assert await stream.next_event() == ("seq", f'{{"seq": {seq}}}')

        response = await asyncio.to_thread(
            share_op,
            public,
            shared["token"],
            {"type": "item.add", "list_uid": shared["list_uid"], "name": "tea"},
        )
        assert await stream.next_event() == ("seq", f'{{"seq": {response["seq"]}}}')

        await asyncio.to_thread(reset_link, room, shared["slug"], shared["list_uid"])
        assert await stream.next_event() == ("revoked", "{}")
        assert await stream.ended()

    run(test)


def test_share_stream_with_a_bad_token_is_a_401_json_error(shared):
    async def test() -> None:
        stream = share_stream("x" * 43)
        await stream.open()
        assert stream.status == 401
        assert b'"share_unavailable"' in await stream.body()

    run(test)
