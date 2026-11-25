"""Share routes over HTTP. Tests use Bun and disposable SQLite data."""

import json
import re
from pathlib import Path
from uuid import uuid4

import httpx2 as httpx
import pytest
from test_typescript_room_access import (
    assert_error,
    assert_headers,
    client_for,
    session_path,
    sign_in,
    storage,
)
from test_typescript_room_feed import add_item, apply, create_list, feed
from test_typescript_room_ops import answer, copy_db, member, op

from conftest import TestServer, TypeScriptTestServer

pytestmark = pytest.mark.own_server


@pytest.fixture(autouse=True)
def typescript_only(pytestconfig: pytest.Config) -> None:
    if pytestconfig.getoption("--browser-backend") != "typescript":
        pytest.skip("Run with --browser-backend typescript after bun run build:ts")


def share_link_path(room: str, uid: str) -> str:
    return f"{room}/lists/{uid}/share-link"


def share_path(client: httpx.Client, room: str, uid: str) -> str:
    response = client.get(share_link_path(room, uid))
    assert response.status_code == 200, response.text
    assert_headers(response)
    assert set(response.json()) == {"token"}
    return "/api/v1/share/" + response.json()["token"]


def create_other_room(server: TestServer) -> str:
    with storage(server) as db:
        db.execute(
            "INSERT INTO rooms (name, slug, password_hash) "
            "SELECT 'Private room', 'other', password_hash FROM rooms WHERE slug = ?",
            (server.room_slug,),
        )
    return "/api/v1/rooms/other"


def test_feed_exposes_one_list_and_only_current_room_navigation(
    server: TypeScriptTestServer,
) -> None:
    # ShareLink fields, ReadSharedList and PublicList actor and scoping.
    slug = server.room_slug
    room = f"/api/v1/rooms/{slug}"
    with member(server) as owner, client_for(server.url) as visitor:
        other = create_other_room(server)
        shared_uid = create_list(owner, room, "Visible")["result"]["list_uid"]
        hidden_uid = create_list(owner, room, "Hidden")["result"]["list_uid"]
        add_item(owner, room, hidden_uid, "hidden item")
        item = add_item(owner, room, shared_uid, "visible item")
        share = share_path(owner, room, shared_uid)
        public = feed(visitor, share, 0)
        assert public["full"] and public["room"] is None and public["deletions"] == []
        assert [(row["uid"], row["slug"], row["name"]) for row in public["lists"]] == [
            (shared_uid, "", "Visible")
        ]
        assert [(row["uid"], row["list_uid"]) for row in public["items"]] == [
            (item, shared_uid)
        ]
        response = visitor.get(f"{share}/changes?since=0")
        assert "set-cookie" not in response.headers
        assert slug not in response.text and '"Home"' not in response.text
        assert_error(visitor.get(f"{room}/changes?since=0"), 401, "not_authenticated")

        assert sign_in(visitor, "other", server.password).status_code == 200
        assert feed(visitor, share, 2**63 - 1) == public
        foreign_list = create_list(visitor, other)["result"]["list_uid"]
        assert_error(
            owner.get(share_link_path(room, foreign_list)), 404, "list_unavailable"
        )

        member_feed = feed(owner, share, public["seq"])
        assert member_feed == public | {"room": {"slug": slug, "name": "Home"}}
        cookie = owner.get(f"{share}/changes?since=0").request.headers["cookie"]
        changed = owner.post(
            f"{room}/password",
            json={
                "current_password": server.password,
                "new_password": "new test password",
            },
        )
        assert changed.status_code == 200, changed.text
        assert share_path(owner, room, shared_uid) == share
        stale = visitor.get(f"{share}/changes?since=0", headers={"Cookie": cookie})
        assert stale.json() == public
        for method in ("GET", "POST"):
            body = {"json": {}} if method == "POST" else {}
            assert_error(
                visitor.request(
                    method,
                    share_link_path(room, shared_uid),
                    headers={"Cookie": cookie},
                    **body,
                ),
                401,
                "not_authenticated",
            )

        for invalid in ("", "?since=", "?since=-1", "?since=1.5", f"?since={2**63}"):
            assert_error(
                visitor.get(f"{share}/changes{invalid}"), 422, "invalid_request"
            )
        for bad in ("short", "A" * 43):
            assert_error(
                visitor.get(f"/api/v1/share/{bad}/changes?since=0"),
                401,
                "share_unavailable",
            )


def test_room_link_controls_and_rotation(server: TypeScriptTestServer) -> None:
    # ReadCurrentLink, RotateLink, RoomShareControls and revocation before replay.
    room = f"/api/v1/rooms/{server.room_slug}"
    with member(server) as owner, client_for(server.url) as visitor:
        other = create_other_room(server)
        list_uid = create_list(owner, room)["result"]["list_uid"]
        link = share_link_path(room, list_uid)
        old = share_path(owner, room, list_uid)
        assert share_path(owner, room, list_uid.replace("-", "")) == old
        assert (
            visitor.post(
                "/api/v1/admin/session", json={"password": server.password}
            ).status_code
            == 200
        )
        assert_error(visitor.get(link), 401, "not_authenticated")
        assert_error(visitor.post(link, json={}), 401, "not_authenticated")
        assert sign_in(visitor, "other", server.password).status_code == 200
        assert_error(visitor.get(link), 401, "not_authenticated")
        assert_error(visitor.post(link, json={}), 401, "not_authenticated")
        foreign_scope = share_link_path(other, list_uid)
        assert_error(visitor.get(foreign_scope), 404, "list_unavailable")
        assert_error(visitor.post(foreign_scope, json={}), 404, "list_unavailable")
        assert_error(
            owner.get(share_link_path(room, "bad-uuid")), 404, "list_unavailable"
        )
        assert_error(owner.post(link, json={"extra": True}), 422, "invalid_request")
        assert_error(
            owner.post(link, json={}, headers={"Origin": "https://elsewhere.test"}),
            403,
            "forbidden_origin",
        )
        assert share_path(owner, room, list_uid) == old

        write = op("item.add", list_uid=list_uid, name="one item")
        saved = answer(visitor, f"{old}/ops", write)
        assert saved["status"] == "applied"
        before = feed(visitor, old, 0)
        stored = server.query("SELECT * FROM processed_ops ORDER BY op_id")
        tokens = {old}
        current = old
        for _ in range(2):
            response = owner.post(link, json={})
            assert response.status_code == 200, response.text
            assert_headers(response)
            assert set(response.json()) == {"token"}
            token = response.json()["token"]
            assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
            assert_error(
                visitor.get(f"{current}/changes?since=0"), 401, "share_unavailable"
            )
            assert_error(
                visitor.post(f"{current}/ops", json=write), 401, "share_unavailable"
            )
            assert_error(
                visitor.post(
                    f"{current}/ops",
                    json=op("item.add", list_uid=list_uid, name="revoked"),
                ),
                401,
                "share_unavailable",
            )
            current = share_path(owner, room, list_uid)
            assert current == f"/api/v1/share/{token}" and current not in tokens
            tokens.add(current)
            after = feed(visitor, current, 0)
            assert after["seq"] > before["seq"]
            assert after["lists"] == [
                before["lists"][0] | {"changed_seq": after["seq"]}
            ]
            assert after == before | {"seq": after["seq"], "lists": after["lists"]}
            before = after
            assert answer(visitor, f"{current}/ops", write) == saved
            assert owner.get(session_path(server.room_slug)).status_code == 200
        assert server.query("SELECT * FROM processed_ops ORDER BY op_id") == stored
        assert server.query("SELECT name FROM items") == [("one item",)]


def test_share_cursor_ignores_other_lists_and_keeps_deletion_floor(
    server: TypeScriptTestServer,
) -> None:
    room = f"/api/v1/rooms/{server.room_slug}"
    with member(server) as owner, client_for(server.url) as visitor:
        list_uid = create_list(owner, room)["result"]["list_uid"]
        other_uid = create_list(owner, room, "Other")["result"]["list_uid"]
        share = share_path(owner, room, list_uid)
        original = feed(visitor, share, 0)
        added = apply(visitor, share, "item.add", list_uid=list_uid, name="Milk")
        added_feed = feed(visitor, share, 0)
        assert original["seq"] < added["seq"] == added_feed["seq"]
        item_uid = added["result"]["item_uid"]
        [item] = added_feed["items"]
        deleted = apply(
            visitor, share, "item.delete", list_uid=list_uid, item_uid=item_uid
        )
        cursor = deleted["seq"]
        assert cursor > added["seq"]
        result = feed(visitor, share, 0)
        assert result["seq"] == cursor and result["items"] == result["deletions"] == []
        other_item = add_item(owner, room, other_uid, "other item")
        apply(owner, room, "item.delete", list_uid=other_uid, item_uid=other_item)
        assert feed(owner, room, 0)["seq"] > cursor
        assert feed(visitor, share, 2**63 - 1) == result
        server.stop()
        with storage(server) as db:
            db.execute(
                "UPDATE deletions SET created_at = '2000-01-01' WHERE uid = ?",
                (item_uid,),
            )
        server.start()
        assert server.query("SELECT uid FROM deletions") == [(other_item,)]
        assert server.query("SELECT list_uid, changed_seq FROM share_seq_floors") == [
            (list_uid, cursor)
        ]
        assert feed(visitor, share, cursor) == result
        # A new refusal after pruning still carries the feed cursor.
        refused = answer(
            visitor, f"{share}/ops", op("item.add", list_uid=list_uid, name=" ")
        )
        assert refused["code"] == "invalid_name" and refused["seq"] == cursor
        undo = op(
            "item.restore",
            list_uid=list_uid,
            **{
                field: item[field]
                for field in (
                    "name",
                    "description",
                    "done",
                    "quantity",
                    "tags",
                    "completed_at",
                    "add_count",
                    "added_at",
                )
            },
        )
        restored = answer(visitor, f"{share}/ops", undo)
        assert restored["status"] == "applied" and restored["seq"] > cursor
        restored_uid = restored["result"]["item_uid"]
        assert restored_uid != item_uid
        assert feed(visitor, share, 0)["items"] == [
            item | {"uid": restored_uid, "changed_seq": restored["seq"]}
        ]
        assert answer(visitor, f"{share}/ops", undo) == restored


def test_replay_across_room_and_share_requires_matching_list_and_room(
    server: TypeScriptTestServer,
) -> None:
    # ApplyOnce: exact saved answer in both directions; no disclosure outside its scope.
    room = f"/api/v1/rooms/{server.room_slug}"
    with (
        member(server) as owner,
        client_for(server.url) as visitor,
        client_for(server.url) as other,
    ):
        other_room = create_other_room(server)
        list_uid = create_list(owner, room)["result"]["list_uid"]
        sibling_uid = create_list(owner, room, "Sibling")["result"]["list_uid"]
        item_uid = add_item(owner, room, list_uid, "Milk")
        share = share_path(owner, room, list_uid)
        sibling_share = share_path(owner, room, sibling_uid)
        assert sign_in(other, "other", server.password).status_code == 200
        other_uid = create_list(other, other_room)["result"]["list_uid"]
        other_share = share_path(other, other_room, other_uid)
        target = {"list_uid": list_uid, "item_uid": item_uid}
        room_first = op("item.quantity_delta", **target, delta=2)
        share_first = op("item.quantity_delta", **target, delta=3)
        room_answer = answer(owner, f"{room}/ops", room_first)
        share_answer = answer(visitor, f"{share}/ops", share_first)
        assert room_answer["status"] == share_answer["status"] == "applied"
        assert (
            answer(visitor, f"{share}/ops", dict(reversed(room_first.items())))
            == room_answer
        )
        assert answer(owner, f"{room}/ops", share_first) == share_answer
        assert answer(visitor, f"{share}/ops", share_first) == share_answer
        assert_error(
            visitor.post(f"{share}/ops", json=share_first | {"delta": 4}),
            409,
            "op_id_reused",
        )
        for path in (sibling_share, other_share):
            assert_error(
                visitor.post(f"{path}/ops", json=room_first), 409, "op_id_reused"
            )
            assert_error(
                visitor.post(f"{path}/ops", json=share_first), 409, "op_id_reused"
            )
        assert_error(
            other.post(f"{other_room}/ops", json=share_first), 409, "op_id_reused"
        )
        assert server.query(
            "SELECT quantity FROM items WHERE uid = ?", (item_uid,)
        ) == [(6,)]


@pytest.mark.parametrize("target", ["missing-list", "sibling-list", "in-scope-list"])
def test_share_first_business_refusal_replay_scope(
    server: TypeScriptTestServer, target: str
) -> None:
    # Grouped R1 regression. No in-scope list means a stored refusal, but no share replay.
    room = f"/api/v1/rooms/{server.room_slug}"
    with member(server) as owner, client_for(server.url) as visitor:
        shared_uid = create_list(owner, room)["result"]["list_uid"]
        sibling_uid = create_list(owner, room, "Sibling")["result"]["list_uid"]
        share = share_path(owner, room, shared_uid)
        list_uid = {
            "missing-list": str(uuid4()),
            "sibling-list": sibling_uid,
            "in-scope-list": shared_uid,
        }[target]
        before = feed(visitor, share, 0)
        body = op(
            "item.quantity_delta", list_uid=list_uid, item_uid=str(uuid4()), delta=1
        )
        first = answer(visitor, f"{share}/ops", body)
        in_scope = target == "in-scope-list"
        assert first["status"] == "rejected" and first["seq"] == before["seq"]
        assert first["code"] == ("item_not_found" if in_scope else "list_unavailable")
        query = "SELECT request_hash, response_json FROM processed_ops WHERE op_id = ?"
        stored = server.query(query, (body["op_id"],))
        [(fingerprint, response_json)] = stored
        assert fingerprint.split(":")[1] == (shared_uid if in_scope else "-")
        assert json.loads(response_json) == first
        if in_scope:
            assert answer(visitor, f"{share}/ops", body) == first
            assert answer(owner, f"{room}/ops", body) == first
        else:
            assert_error(visitor.post(f"{share}/ops", json=body), 409, "op_id_reused")
        assert server.query(query, (body["op_id"],)) == stored
        assert feed(visitor, share, 0) == before


@pytest.mark.parametrize("target", ["sibling-list", "in-scope-list"])
def test_share_checks_list_scope_before_item_uid_collision(
    server: TypeScriptTestServer, target: str
) -> None:
    room = f"/api/v1/rooms/{server.room_slug}"
    with member(server) as owner, client_for(server.url) as visitor:
        shared_uid = create_list(owner, room)["result"]["list_uid"]
        sibling_uid = create_list(owner, room, "Sibling")["result"]["list_uid"]
        item = apply(owner, room, "item.add", list_uid=sibling_uid, name="Existing")[
            "result"
        ]
        share = share_path(owner, room, shared_uid)
        path = f"{share}/ops"
        list_uid = sibling_uid if target == "sibling-list" else shared_uid
        body = op("item.add", list_uid=list_uid, uid=item["item_uid"], name="New")
        if target == "sibling-list":
            first = answer(visitor, path, body)
            assert first["status"] == "rejected" and first["code"] == "list_unavailable"
            assert_error(visitor.post(path, json=body), 409, "op_id_reused")
        else:
            assert_error(visitor.post(path, json=body), 422, "invalid_request")
            assert (
                server.query(
                    "SELECT 1 FROM processed_ops WHERE op_id=?", (body["op_id"],)
                )
                == []
            )
        assert server.query("SELECT name FROM items") == [("Existing",)]


def test_share_request_errors_do_not_consume_ids(server: TypeScriptTestServer) -> None:
    room = f"/api/v1/rooms/{server.room_slug}"
    with member(server) as owner, client_for(server.url) as visitor:
        list_uid = create_list(owner, room)["result"]["list_uid"]
        share_ops = f"{share_path(owner, room, list_uid)}/ops"
        safe = op("item.add", list_uid=list_uid, name="Milk")
        stored = server.query("SELECT * FROM processed_ops ORDER BY op_id")
        for body in (
            op("room.rename", name="Private rename"),
            op("list.create", name="Private list"),
            op("list.rename", list_uid=list_uid, name="Private rename", base_seq=0),
            op("list.delete", list_uid=list_uid),
            safe | {"extra": True},
        ):
            assert_error(visitor.post(share_ops, json=body), 422, "invalid_request")
        assert_error(
            visitor.post(
                share_ops, json=safe, headers={"Origin": "https://elsewhere.test"}
            ),
            403,
            "forbidden_origin",
        )
        assert_error(
            visitor.post(
                share_ops, content="{}", headers={"Content-Type": "text/plain"}
            ),
            415,
            "invalid_request",
        )
        assert_error(
            visitor.post("/api/v1/share/short/ops", json=safe), 401, "share_unavailable"
        )
        assert server.query("SELECT * FROM processed_ops ORDER BY op_id") == stored
        assert answer(visitor, share_ops, safe)["status"] == "applied"


@pytest.mark.parametrize("delete", ["list", "room"])
def test_deletion_revokes_share_before_replay(
    server: TypeScriptTestServer, delete: str
) -> None:
    room = f"/api/v1/rooms/{server.room_slug}"
    with member(server) as owner, client_for(server.url) as visitor:
        list_uid = create_list(owner, room)["result"]["list_uid"]
        share = share_path(owner, room, list_uid)
        body = op("item.add", list_uid=list_uid, name="gone")
        assert answer(visitor, f"{share}/ops", body)["status"] == "applied"
        if delete == "list":
            apply(owner, room, "list.delete", list_uid=list_uid)
            assert_error(
                owner.get(share_link_path(room, list_uid)), 404, "list_unavailable"
            )
        else:
            assert (
                owner.request(
                    "DELETE", room, json={"password": server.password}
                ).status_code
                == 204
            )
        assert_error(visitor.get(f"{share}/changes?since=0"), 401, "share_unavailable")
        assert_error(visitor.post(f"{share}/ops", json=body), 401, "share_unavailable")
        assert not server.query("SELECT * FROM items")


def test_share_tag_and_visibility_ops_use_list_scope(
    server: TypeScriptTestServer,
) -> None:
    # Combined .11 + .12 gate: real dispatcher, feed and replay, with no stubs.
    room = f"/api/v1/rooms/{server.room_slug}"
    with member(server) as owner, client_for(server.url) as visitor:
        list_uid = create_list(owner, room)["result"]["list_uid"]
        sibling_uid = create_list(owner, room, "Sibling")["result"]["list_uid"]
        item_uid = add_item(owner, room, list_uid, "Milk")
        share = share_path(owner, room, list_uid)
        sibling = share_path(owner, room, sibling_uid)
        tag = op("list.tag_add", list_uid=list_uid, tag="Fresh")
        tagged = answer(visitor, f"{share}/ops", tag)
        assert tagged["status"] == "applied"
        assert answer(owner, f"{room}/ops", tag) == tagged
        assert_error(visitor.post(f"{sibling}/ops", json=tag), 409, "op_id_reused")
        cross = answer(
            visitor,
            f"{share}/ops",
            op("list.tag_add", list_uid=sibling_uid, tag="Hidden"),
        )
        assert cross["status"] == "rejected" and cross["code"] == "list_unavailable"
        assert feed(visitor, sibling, 0)["lists"][0]["tags"] == []

        for kind, fields in (
            (
                "list.tag_settings",
                {"mode": "single", "show_on_items": False, "only_item_tags": True},
            ),
            ("item.toggle_tag", {"tag": "Fresh", "item_uid": item_uid, "active": True}),
            ("list.tag_color", {"tag": "Fresh", "color": 2}),
            ("list.tag_rename", {"tag": "Fresh", "new_tag": "Produce"}),
            ("list.visibility", {"mode": "recent", "recent_count": 3}),
        ):
            saved = apply(visitor, share, kind, list_uid=list_uid, **fields)
            shared = feed(visitor, share, 0)
            assert saved["seq"] == shared["seq"]
        [row] = shared["lists"]
        assert row["tags"] == shared["items"][0]["tags"] == ["Produce"]
        assert row["tag_settings"] == {
            "mode": "single",
            "show_on_items": False,
            "only_item_tags": True,
            "colors": {"Produce": 2},
        }
        assert (row["hide_done"]["mode"], row["hide_done"]["recent_count"]) == (
            "recent",
            3,
        )
        removed = apply(
            visitor, share, "list.tag_remove", list_uid=list_uid, tag="Produce"
        )
        shared = feed(visitor, share, 0)
        assert removed["seq"] == shared["seq"]
        assert shared["lists"][0]["tags"] == shared["items"][0]["tags"] == []


def test_existing_token_works_but_legacy_answer_does_not_replay(tmp_path: Path) -> None:
    # Python creates the legacy data only. Check Bun behavior against the spec.
    for name in ("python", "bun"):
        (tmp_path / name).mkdir()
    reference = TestServer(tmp_path / "python")
    bun = TypeScriptTestServer(tmp_path / "bun")
    try:
        reference.start()
        room = f"/api/v1/rooms/{reference.room_slug}"
        with member(reference) as owner:
            list_uid = create_list(owner, room)["result"]["list_uid"]
            item_uid = add_item(owner, room, list_uid, "Existing")
            share = share_path(owner, room, list_uid)
            legacy = op(
                "item.quantity_delta", list_uid=list_uid, item_uid=item_uid, delta=4
            )
            assert answer(owner, f"{room}/ops", legacy)["status"] == "applied"
        copy_db(reference, bun)
        bun.start()
        with member(bun) as owner, client_for(bun.url) as visitor:
            assert share_path(owner, room, list_uid) == share
            [saved_item] = feed(visitor, share, 0)["items"]
            assert (saved_item["uid"], saved_item["name"], saved_item["quantity"]) == (
                item_uid,
                "Existing",
                5,
            )
            query = (
                "SELECT request_hash, response_json FROM processed_ops WHERE op_id = ?"
            )
            stored = bun.query(query, (legacy["op_id"],))
            assert re.fullmatch(r"[0-9a-f]{64}", stored[0][0])
            assert_error(visitor.post(f"{share}/ops", json=legacy), 409, "op_id_reused")
            assert bun.query(query, (legacy["op_id"],)) == stored
            assert bun.query("SELECT quantity FROM items") == [(5,)]
    finally:
        bun.stop()
        reference.stop()
