"""Tag and visibility obligations against Bun HTTP routes and disposable SQLite."""

import sqlite3
from contextlib import closing
from uuid import uuid4

import pytest
from test_typescript_room_feed import (
    add_item,
    apply,
    create_list,
    feed,
)
from test_typescript_room_feed import typescript_only as typescript_only
from test_typescript_room_ops import answer, member, op, reused

from conftest import TypeScriptTestServer

pytestmark = pytest.mark.own_server


def test_tag_name_limits_and_business_refusals(server: TypeScriptTestServer) -> None:
    # AddListTag, RenameListTag, SetListTagColor, BusinessRefusals, ApplyOnce.
    room = f"/api/v1/rooms/{server.room_slug}"
    path = f"{room}/ops"
    with member(server) as client:
        target = {"list_uid": create_list(client, room)["result"]["list_uid"]}
        apply(client, room, "list.tag_add", **target, tag="  Market  ")
        apply(client, room, "list.tag_add", **target, tag="market")
        for i in range(47):
            apply(client, room, "list.tag_add", **target, tag=f"Extra {i:02}")
        boundary = "🥕" * 30
        before = apply(client, room, "list.tag_add", **target, tag=boundary)["seq"]
        assert (
            apply(client, room, "list.tag_add", **target, tag=boundary)["seq"] == before
        )
        assert (
            apply(client, room, "list.tag_remove", **target, tag="missing")["seq"]
            == before
        )
        assert (
            apply(
                client,
                room,
                "list.tag_rename",
                **target,
                tag="Market",
                new_tag="Market",
            )["seq"]
            == before
        )
        for kind, fields, code in (
            ("list.tag_add", {"tag": "Overflow"}, "too_many"),
            ("list.tag_add", {"tag": "  "}, "invalid_name"),
            ("list.tag_add", {"tag": boundary + "🥕"}, "too_long"),
            ("list.tag_color", {"tag": "missing", "color": 0}, "unknown_tag"),
            ("list.tag_rename", {"tag": "missing", "new_tag": "new"}, "unknown_tag"),
            (
                "list.tag_rename",
                {"tag": "Market", "new_tag": "market"},
                "duplicate_name",
            ),
            (
                "item.toggle_tag",
                {"tag": "Market", "item_uid": str(uuid4())},
                "item_not_found",
            ),
        ):
            body = op(kind, **target, **fields)
            rejected = answer(client, path, body)
            assert (rejected["status"], rejected["code"], rejected["seq"]) == (
                "rejected",
                code,
                before,
            )
            assert answer(client, path, body) == rejected
        absent = op("list.tag_add", list_uid=str(uuid4()), tag="new")
        assert answer(client, path, absent)["code"] == "list_unavailable"
        invalid = op("list.tag_color", **target, tag="Market", color=7)
        assert client.post(path, json=invalid).status_code == 422
        assert not server.query(
            "SELECT 1 FROM processed_ops WHERE op_id = ?", (invalid["op_id"],)
        )
        unchanged = feed(client, room, before)
        assert unchanged["lists"] == unchanged["items"] == unchanged["deletions"] == []
        [row] = feed(client, room, 0)["lists"]
        assert row["tags"] == [
            *[f"Extra {i:02}" for i in range(47)],
            "Market",
            "market",
            boundary,
        ]


def test_tag_bulk_edits_assignment_and_versions(server: TypeScriptTestServer) -> None:
    # ChangeOrUndo, RowVersionCheck, RenameListTag, RemoveListTag, ChangeTagSelection.
    room = f"/api/v1/rooms/{server.room_slug}"
    path = f"{room}/ops"
    with member(server) as client:
        target = {"list_uid": create_list(client, room)["result"]["list_uid"]}
        milk = {
            **target,
            "item_uid": add_item(client, room, target["list_uid"], "milk"),
        }
        eggs = {
            **target,
            "item_uid": add_item(client, room, target["list_uid"], "eggs"),
        }
        other = create_list(client, room, "Other")["result"]["list_uid"]
        foreign = add_item(client, room, other, "bread")
        assert (
            answer(
                client, path, op("item.toggle_tag", **target, item_uid=foreign, tag="A")
            )["code"]
            == "item_not_found"
        )
        apply(
            client, room, "item.toggle_tag", list_uid=other, item_uid=foreign, tag="A"
        )
        for tag in ("Z", "A"):
            apply(client, room, "list.tag_add", **target, tag=tag)
        apply(client, room, "list.tag_color", **target, tag="A", color=6)
        for tag in ("Z", "A", "B"):
            apply(client, room, "item.toggle_tag", **milk, tag=tag, active=True)
        before = apply(client, room, "item.toggle_tag", **eggs, tag="A", active=True)[
            "seq"
        ]
        renamed = apply(
            client, room, "list.tag_rename", **target, tag="A", new_tag=" B "
        )
        delta = feed(client, room, before)
        [row] = delta["lists"]
        assert row["changed_seq"] == renamed["result"]["changed_seq"]
        assert row["tags"] == ["B", "Z"] and row["tag_settings"]["colors"] == {"B": 6}
        assert {i["uid"]: i["tags"] for i in delta["items"]} == {
            milk["item_uid"]: ["Z", "B"],
            eggs["item_uid"]: ["B"],
        }
        cursor = delta["seq"]
        returned = feed(client, room, cursor)
        assert returned["seq"] == cursor and not returned["full"]
        assert returned["lists"] == returned["items"] == returned["deletions"] == []
        stale = op("item.edit", **milk, base_seq=before, name="cream", description="")
        assert answer(client, path, stale)["code"] == "changed_meanwhile"
        hidden = apply(client, room, "list.tag_settings", **target, show_on_items=False)
        next_delta = feed(client, room, returned["seq"])
        assert next_delta["seq"] == hidden["seq"] and not next_delta["full"]
        assert not next_delta["items"]
        assert not next_delta["lists"][0]["tag_settings"]["show_on_items"]
        before_single = apply(
            client, room, "list.tag_settings", **target, only_item_tags=True
        )["seq"]
        single = apply(client, room, "list.tag_settings", **target, mode="single")
        delta = feed(client, room, before_single)
        assert [i["tags"] for i in delta["items"]] == [["B"]]
        assert delta["lists"][0]["tag_settings"] == {
            "mode": "single",
            "show_on_items": False,
            "only_item_tags": True,
            "colors": {"B": 6},
        }
        assert (
            apply(client, room, "item.toggle_tag", **milk, tag="B", active=True)["seq"]
            == single["seq"]
        )
        applied = apply(client, room, "item.toggle_tag", **milk, tag="Z", active=True)
        assert [i["tags"] for i in feed(client, room, single["seq"])["items"]] == [
            ["Z"]
        ]
        assert (
            apply(client, room, "item.toggle_tag", **milk, tag="B", active=False)["seq"]
            == applied["seq"]
        )
        removed = apply(client, room, "list.tag_remove", **target, tag="B")
        delta = feed(client, room, applied["seq"])
        assert delta["seq"] == removed["seq"]
        [row] = delta["lists"]
        assert row["tags"] == ["Z"] and row["tag_settings"]["colors"] == {}
        assert [(i["uid"], i["tags"]) for i in delta["items"]] == [
            (eggs["item_uid"], [])
        ]
        apply(client, room, "list.tag_add", **target, tag="B")
        full = {i["uid"]: i["tags"] for i in feed(client, room, 0)["items"]}
        assert full == {milk["item_uid"]: ["Z"], eggs["item_uid"]: [], foreign: ["A"]}


def test_new_tag_starts_empty_with_legacy_assignments(
    server: TypeScriptTestServer,
) -> None:
    # AddListTag. Simulate a database where Python removed Market but left assignments.
    room = f"/api/v1/rooms/{server.room_slug}"
    with member(server) as client:
        uid = create_list(client, room)["result"]["list_uid"]
        item = add_item(client, room, uid, "milk")
        other = create_list(client, room, "Other")["result"]["list_uid"]
        foreign = add_item(client, room, other, "bread")
        with closing(sqlite3.connect(server.database)) as db, db:
            db.execute(
                "UPDATE items SET active_tags = ? WHERE uid IN (?, ?)",
                ('["Market", "market"]', item, foreign),
            )
        before = feed(client, room, 0)
        assert {i["uid"]: i["tags"] for i in before["items"]} == {
            item: ["Market", "market"],
            foreign: ["Market", "market"],
        }
        added = apply(client, room, "list.tag_add", list_uid=uid, tag=" Market ")
        delta = feed(client, room, before["seq"])
        assert delta["seq"] == added["seq"]
        [row] = delta["lists"]
        assert (row["uid"], row["tags"], row["changed_seq"]) == (
            uid,
            ["Market"],
            added["result"]["changed_seq"],
        )
        [changed] = delta["items"]
        assert (changed["uid"], changed["tags"], changed["changed_seq"]) == (
            item,
            ["market"],
            added["seq"],
        )
        assert changed["changed_seq"] > row["changed_seq"] > before["seq"]
        # An explicit assignment (as used by Undo) can restore it. Adding the
        # existing tag again, even with a fresh op ID, does not clear that work.
        restored = apply(
            client,
            room,
            "item.toggle_tag",
            list_uid=uid,
            item_uid=item,
            tag="Market",
            active=True,
        )
        assert (
            apply(client, room, "list.tag_add", list_uid=uid, tag="Market")["seq"]
            == restored["seq"]
        )
        assert {i["uid"]: i["tags"] for i in feed(client, room, 0)["items"]} == {
            item: ["market", "Market"],
            foreign: ["Market", "market"],
        }


def test_tag_toggle_replay_and_retention(server: TypeScriptTestServer) -> None:
    # SetItemTag, ChangeOrUndo, ApplyOnce, AnswerRetention.
    room = f"/api/v1/rooms/{server.room_slug}"
    path = f"{room}/ops"
    with member(server) as client:
        uid = create_list(client, room)["result"]["list_uid"]
        item = add_item(client, room, uid, "milk")
        target = {"list_uid": uid, "item_uid": item, "tag": "Market"}
        turn_on = op("item.toggle_tag", **target, active=True)
        applied = answer(client, path, turn_on)
        assert applied["result"]["changed_seq"] == applied["seq"]
        assert (
            apply(client, room, "item.toggle_tag", **target, active=True)["seq"]
            == applied["seq"]
        )
        toggle = op("item.toggle_tag", **target)
        off = answer(client, path, toggle)
        assert feed(client, room, applied["seq"])["items"][0]["tags"] == []
        assert answer(client, path, toggle) == off
        assert (
            answer(client, path, turn_on) == applied
        )  # Replay does not turn it on again.
        reused(client, path, toggle | {"active": True})
        reused(client, path, toggle | {"active": None})
        assert feed(client, room, off["seq"])["items"] == []

    server.stop()
    with closing(sqlite3.connect(server.database)) as db, db:
        db.execute(
            "UPDATE processed_ops SET created_at = '2000-01-01' WHERE op_id = ?",
            (toggle["op_id"],),
        )
    server.start()
    with member(server) as client:
        assert not server.query(
            "SELECT 1 FROM processed_ops WHERE op_id = ?", (toggle["op_id"],)
        )
        assert answer(client, path, turn_on) == applied
        assert answer(client, path, toggle)["seq"] > off["seq"]
        assert feed(client, room, off["seq"])["items"][0]["tags"] == ["Market"]


def test_visibility_merges_settings_without_filtering_feed(
    server: TypeScriptTestServer,
) -> None:
    # ChangeCheckedVisibility, CheckedVisibility, RowVersionCheck.
    room = f"/api/v1/rooms/{server.room_slug}"
    path = f"{room}/ops"
    with member(server) as client:
        created = create_list(client, room)
        uid = created["result"]["list_uid"]
        milk = add_item(client, room, uid, "milk")
        checked = apply(
            client, room, "item.set_done", list_uid=uid, item_uid=milk, done=True
        )
        apply(
            client,
            room,
            "list.visibility",
            list_uid=uid,
            age_days=1,
            recent_count=100_000,
        )
        for value in (0, 100_001, 1.5):
            invalid = op("list.visibility", list_uid=uid, age_days=value)
            assert client.post(path, json=invalid).status_code == 422
        before = apply(client, room, "list.visibility", list_uid=uid, mode="all")["seq"]
        assert (
            apply(client, room, "list.visibility", list_uid=uid, mode="all")["seq"]
            == before
        )
        stale = op(
            "list.rename", list_uid=uid, name="New name", base_seq=created["seq"]
        )
        assert answer(client, path, stale)["code"] == "changed_meanwhile"
        assert feed(client, room, checked["seq"])["items"] == []
        full = feed(client, room, 0)
        assert full["lists"][0]["hide_done"] == {
            "mode": "all",
            "age_days": 1,
            "recent_count": 100_000,
        }
        [item] = full["items"]
        assert item["uid"] == milk and item["done"] and item["completed_at"]
        apply(client, room, "list.visibility", list_uid=uid, mode="off")
        assert feed(client, room, 0)["lists"][0]["hide_done"] == {
            "mode": "off",
            "age_days": 1,
            "recent_count": 100_000,
        }
