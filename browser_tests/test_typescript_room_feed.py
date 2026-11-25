"""Room feed obligations over HTTP, using only disposable SQLite databases."""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest
from test_typescript_room_ops import answer, copy_db, member, op

from conftest import TestServer, TypeScriptTestServer

pytestmark = pytest.mark.own_server


@pytest.fixture(autouse=True)
def typescript_only(pytestconfig: pytest.Config) -> None:
    if pytestconfig.getoption("--browser-backend") != "typescript":
        pytest.skip("Build and select the TypeScript backend")


def feed(client: httpx.Client, room: str, since: int) -> dict[str, Any]:
    response = client.get(f"{room}/changes", params={"since": since})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def apply(client: httpx.Client, room: str, kind: str, **fields: Any) -> dict[str, Any]:
    result = answer(client, f"{room}/ops", op(kind, **fields))
    assert result["status"] == "applied", result
    return result


def create_list(client: httpx.Client, room: str, name: str = "Shop") -> dict[str, Any]:
    return apply(client, room, "list.create", name=name)


def add_item(client: httpx.Client, room: str, list_uid: str, name: str) -> str:
    return apply(client, room, "item.add", list_uid=list_uid, name=name)["result"][
        "item_uid"
    ]


def test_room_feed_from_real_writes(server: TypeScriptTestServer) -> None:
    # ReadFullRoom, ReadRoomDelta, FeedAndCursorAgree.
    slug = server.room_slug
    room = f"/api/v1/rooms/{slug}"
    with member(server) as client:
        assert feed(client, room, 0) == {
            "seq": 0,
            "full": True,
            "room": {"slug": slug, "name": "Home"},
            "lists": [],
            "items": [],
            "deletions": [],
        }
        created = create_list(client, room)
        list_uid = created["result"]["list_uid"]
        milk = add_item(client, room, list_uid, "milk")
        bread = add_item(client, room, list_uid, "bread")
        delta = feed(client, room, created["seq"])
        assert not delta["full"] and delta["lists"] == delta["deletions"] == []
        assert [row["uid"] for row in delta["items"]] == [milk, bread]
        assert delta["items"][0]["changed_seq"] < delta["items"][1]["changed_seq"]
        before = delta["seq"]
        assert delta["items"][1]["changed_seq"] == before
        full = feed(client, room, 0)
        assert full["seq"] == before and full["full"] and full["deletions"] == []
        assert [row["uid"] for row in full["lists"]] == [list_uid]
        assert full["items"] == delta["items"]

        renamed = apply(client, room, "room.rename", name="Pantry")["seq"]
        assert feed(client, room, before) == {
            "seq": renamed,
            "full": False,
            "room": {"slug": slug, "name": "Pantry"},
            "lists": [],
            "items": [],
            "deletions": [],
        }
        list_renamed = apply(
            client,
            room,
            "list.rename",
            list_uid=list_uid,
            name="Groceries",
            base_seq=created["seq"],
        )["seq"]
        delta = feed(client, room, renamed)
        assert delta["seq"] == list_renamed and not delta["full"]
        assert delta["items"] == delta["deletions"] == []
        assert [
            (row["uid"], row["name"], row["changed_seq"]) for row in delta["lists"]
        ] == [(list_uid, "Groceries", list_renamed)]
        removed = apply(client, room, "item.delete", list_uid=list_uid, item_uid=milk)[
            "seq"
        ]
        assert feed(client, room, list_renamed)["deletions"] == [
            {"kind": "item", "uid": milk}
        ]
        deleted = apply(client, room, "list.delete", list_uid=list_uid)["seq"]
        delta = feed(client, room, removed)
        assert delta["seq"] == deleted and not delta["full"]
        assert delta["items"] == delta["lists"] == []
        assert delta["deletions"] == [
            {"kind": "item", "uid": bread},
            {"kind": "list", "uid": list_uid},
        ]
        assert feed(client, room, deleted)["deletions"] == []
        recovered = feed(client, room, deleted + 1)
        assert recovered == feed(client, room, 0) == feed(client, room, 2**63 - 1)
        assert recovered["seq"] == deleted and recovered["full"]
        assert recovered["items"] == recovered["lists"] == recovered["deletions"] == []


def test_room_feed_access_and_query(server: TypeScriptTestServer) -> None:
    # RoomChanges is only available to a current session of this room.
    slug = server.room_slug
    room = f"/api/v1/rooms/{slug}"
    with member(server) as client, httpx.Client(base_url=server.url) as stranger:
        response = stranger.get(f"{room}/changes?since=0")
        assert response.status_code == 401
        denied = response.json()
        assert denied["error"]["code"] == "not_authenticated"
        for query in (
            "",
            "?since=",
            "?since=-1",
            "?since=no",
            "?since=1.5",
            f"?since={2**63}",
        ):
            bad = client.get(f"{room}/changes{query}")
            assert bad.status_code == 422
            assert bad.json()["error"]["code"] == "invalid_request"

        with closing(sqlite3.connect(server.database)) as db, db:
            db.execute(
                "INSERT INTO rooms(name, slug, password_hash) "
                "SELECT 'Other', 'other', password_hash FROM rooms WHERE slug=?",
                (slug,),
            )
            # The other room also has rows worth leaking.
            db.execute(
                "INSERT INTO lists(name, slug, room_id, share_token) "
                "SELECT 'Private', 'private', id, 'test-only' FROM rooms WHERE slug='other'"
            )
        assert feed(client, room, 0)["lists"] == []
        for target in ("other", "unknown"):
            response = client.get(f"/api/v1/rooms/{target}/changes?since=0")
            assert response.status_code == 401 and response.json() == denied

        # Replay the actual cookie after sign-out, not an empty cookie jar.
        cookie = client.get(f"{room}/changes?since=0").request.headers["cookie"]
        assert client.delete(f"{room}/session").status_code == 204
        response = stranger.get(f"{room}/changes?since=0", headers={"Cookie": cookie})
        assert response.status_code == 401 and response.json() == denied


def test_pruned_prefix_recovers_without_moving_the_cursor(
    server: TypeScriptTestServer,
) -> None:
    # An old cursor gets a full snapshot; at the floor, a delta is enough.
    room = f"/api/v1/rooms/{server.room_slug}"
    with member(server) as client:
        list_uid = create_list(client, room)["result"]["list_uid"]
        milk, bread, eggs = [
            add_item(client, room, list_uid, name) for name in ("milk", "bread", "eggs")
        ]
        before = feed(client, room, 0)["seq"]
        delete_seqs = [
            apply(client, room, "item.delete", list_uid=list_uid, item_uid=uid)["seq"]
            for uid in (milk, bread, eggs)
        ]
        _, floor, current = delete_seqs
        assert [row["uid"] for row in feed(client, room, before)["deletions"]] == [
            milk,
            bread,
            eggs,
        ]
        server.stop()
        with closing(sqlite3.connect(server.database)) as db, db:
            db.execute(
                "UPDATE deletions SET created_at = strftime('%Y-%m-%dT%H:%M:%fZ','now','-91 days') WHERE uid=?",
                (bread,),
            )
            db.execute(
                "UPDATE deletions SET created_at = strftime('%Y-%m-%dT%H:%M:%fZ','now','-89 days') WHERE uid=?",
                (eggs,),
            )
        server.start()
        assert server.query("SELECT uid FROM deletions") == [(eggs,)]
        assert server.query("SELECT list_uid, changed_seq FROM share_seq_floors") == [
            (list_uid, floor)
        ]
        assert server.query("SELECT deletions_pruned_seq FROM rooms") == [(floor,)]
        recovered = feed(client, room, before)
        assert recovered == feed(client, room, 0)
        assert (
            recovered["seq"] == current
            and recovered["full"]
            and recovered["deletions"] == []
        )
        assert [row["uid"] for row in recovered["lists"]] == [list_uid]
        delta = feed(client, room, floor)
        assert delta["seq"] == current and not delta["full"]
        assert delta["deletions"] == [{"kind": "item", "uid": eggs}]


def test_sync_reads_on_the_same_existing_data(tmp_path: Path) -> None:
    """Compare a few room reads, not the servers or their whole API."""
    for directory in (tmp_path / "python", tmp_path / "bun"):
        directory.mkdir()
    reference = TestServer(tmp_path / "python")
    bun = TypeScriptTestServer(tmp_path / "bun")
    try:
        reference.start()
        room = f"/api/v1/rooms/{reference.room_slug}"
        with member(reference) as py:
            list_uid = create_list(py, room)["result"]["list_uid"]
            legacy = add_item(py, room, list_uid, "legacy")
            kept = add_item(py, room, list_uid, "kept")
            gone = add_item(py, room, list_uid, "gone")
            before = feed(py, room, 0)["seq"]
            apply(py, room, "item.delete", list_uid=list_uid, item_uid=gone)
            renamed = apply(py, room, "room.rename", name="Pantry")["seq"]
            # Model rows carried through a migration, including lenient stored fields.
            with closing(sqlite3.connect(reference.database)) as db, db:
                db.execute(
                    "UPDATE lists SET changed_seq=0,list_tags=?,tag_colors=? WHERE uid=?",
                    ('["Zoo",2,"apple","Apple"]', '{"Zoo":2}', list_uid),
                )
                [(guard,)] = db.execute(
                    "SELECT sql FROM sqlite_master WHERE name='items_field_rules_update'"
                ).fetchall()
                db.execute("DROP TRIGGER items_field_rules_update")
                db.execute(
                    "UPDATE items SET changed_seq=0, quantity=NULL, description=NULL, "
                    "done=1, completed_at='not a date', active_tags='bad json', added_at=NULL "
                    "WHERE uid=?",
                    (legacy,),
                )
                db.execute(guard)
                db.execute(
                    "UPDATE items SET done=1, completed_at='2024-11-06 08:30:11.123456+01:00', "
                    'active_tags=\'["Zoo",1,"apple"]\' WHERE uid=?',
                    (kept,),
                )
            copy_db(reference, bun)
            bun.start()
            with member(bun) as client:
                full = feed(client, room, 0)
                assert full["lists"][0]["changed_seq"] == 0
                assert full["lists"][0]["tags"] == ["apple", "Apple", "Zoo"]
                old, done = full["items"]
                assert old["uid"] == legacy and old["changed_seq"] == 0
                assert (
                    old["quantity"],
                    old["description"],
                    old["tags"],
                    old["completed_at"],
                ) == (1, "", [], None)
                assert (
                    done["uid"] == kept
                    and done["completed_at"] == "2024-11-06T07:30:11.123456Z"
                )
                assert feed(client, room, before)["deletions"] == [
                    {"kind": "item", "uid": gone}
                ]
                assert feed(client, room, renamed)["full"] is False
                for since in (0, before, renamed, full["seq"], full["seq"] + 1):
                    assert feed(client, room, since) == feed(py, room, since)
                newer = apply(py, room, "room.rename", name="After backup")["seq"]
                assert newer > full["seq"]
                # The client's cursor came from a later write than the Bun copy has.
                assert feed(client, room, newer) == full
    finally:
        bun.stop()
        reference.stop()
