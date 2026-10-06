"""Tag and hide-done ops (docs/api.md, "Operation types")."""

import json
from typing import Any

import pytest
from api_helpers import (
    add_item,
    assert_error,
    changes,
    client_for,
    default_list,
    home,
    item_row,
    list_uid_of,
    new_id,
    op,
    processed_ops_count,
    send,
)
from starlette.testclient import TestClient

import database_crud as crud
import live_updates
from database_setup import db


@pytest.fixture
def room() -> tuple[int, str, TestClient]:
    room_id, slug = home()
    return room_id, slug, client_for(slug)


@pytest.fixture
def notified(monkeypatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(live_updates, "_listeners", [calls.append])
    return calls


def seq_of(room_id: int) -> int:
    return crud.get_room_seq_locked(room_id)


def list_body(op_type: str, list_uid: str, **fields: Any) -> dict:
    return {"op_id": new_id(), "type": op_type, "list_uid": list_uid, **fields}


def feed_list(client: TestClient, slug: str, since: int, list_uid: str) -> dict:
    [found] = [x for x in changes(client, slug, since)["lists"] if x["uid"] == list_uid]
    return found


def stored_tags(list_id: int) -> list[str]:
    raw = db.execute("SELECT list_tags FROM lists WHERE id = ?", (list_id,)).fetchone()
    return json.loads(raw[0]) if raw[0] else []


def item_tags(item_uid: str) -> list[str]:
    return json.loads(item_row(item_uid)["tags"] or "[]")


def visibility(list_id: int) -> tuple[str, int, int]:
    return db.execute(
        "SELECT hide_done_mode, hide_done_age_days, hide_done_recent_count "
        "FROM lists WHERE id = ?",
        (list_id,),
    ).fetchone()


# list.tag_add / list.tag_remove


def test_tag_add(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    crud.add_list_tag(list_id, "market")
    before = seq_of(room_id)
    response = op(client, slug, list_body("list.tag_add", list_uid, tag=" Lidl "))
    assert response["status"] == "applied" and response["result"] == {}
    assert response["seq"] == before + 1
    assert feed_list(client, slug, before, list_uid)["tags"] == ["Lidl", "market"]
    assert stored_tags(list_id) == ["Lidl", "market"]
    assert notified == [room_id]


def test_tag_add_existing_changes_nothing(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    crud.add_list_tag(list_id, "Lidl")
    seq = seq_of(room_id)
    response = op(client, slug, list_body("list.tag_add", list_uid, tag="Lidl"))
    assert response["status"] == "applied"
    assert response["seq"] == seq == seq_of(room_id)
    assert stored_tags(list_id) == ["Lidl"]
    assert notified == [room_id]


def test_tag_add_with_an_empty_tag_is_rejected(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    seq = seq_of(room_id)
    response = op(client, slug, list_body("list.tag_add", list_uid, tag="  "))
    assert response["status"] == "rejected"
    assert response["code"] == "invalid_name"
    assert response["message"] == "Name cannot be empty"
    assert response["seq"] == seq == seq_of(room_id)
    assert stored_tags(list_id) == []
    assert notified == []


def test_tag_remove_keeps_item_tags(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    crud.add_list_tag(list_id, "Lidl")
    crud.add_list_tag(list_id, "Market")
    item_uid = add_item(list_id, "milk")
    crud.toggle_item_active_tag(
        db.execute("SELECT id FROM items").fetchone()[0], list_id, "Lidl"
    )
    before = seq_of(room_id)
    response = op(client, slug, list_body("list.tag_remove", list_uid, tag="Lidl"))
    assert response["status"] == "applied" and response["result"] == {}
    assert feed_list(client, slug, before, list_uid)["tags"] == ["Market"]
    assert item_tags(item_uid) == ["Lidl"]
    assert notified == [room_id]


def test_tag_remove_of_a_missing_tag_changes_nothing(room):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    crud.add_list_tag(list_id, "Lidl")
    seq = seq_of(room_id)
    # Exact match: another case is another tag.
    response = op(client, slug, list_body("list.tag_remove", list_uid, tag="lidl"))
    assert response["status"] == "applied"
    assert seq_of(room_id) == seq
    assert stored_tags(list_id) == ["Lidl"]


def test_tag_undo_is_tag_add(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    crud.add_list_tag(list_id, "Lidl")
    op(client, slug, list_body("list.tag_remove", list_uid, tag="Lidl"))
    op(client, slug, list_body("list.tag_add", list_uid, tag="Lidl"))
    assert stored_tags(list_id) == ["Lidl"]


# item.toggle_tag


def toggle_body(list_uid: str, item_uid: str, tag: str) -> dict:
    return list_body("item.toggle_tag", list_uid, item_uid=item_uid, tag=tag)


def test_toggle_item_tag_on_and_off(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    before = seq_of(room_id)
    response = op(client, slug, toggle_body(list_uid, item_uid, "Lidl"))
    assert response["status"] == "applied" and response["result"] == {}
    changed = changes(client, slug, before)["items"]
    assert [(i["uid"], i["tags"]) for i in changed] == [(item_uid, ["Lidl"])]
    op(client, slug, toggle_body(list_uid, item_uid, "Market"))
    assert item_tags(item_uid) == ["Lidl", "Market"]
    op(client, slug, toggle_body(list_uid, item_uid, "Lidl"))
    assert item_tags(item_uid) == ["Market"]
    assert notified == [room_id] * 3


def test_toggle_uses_the_stored_tags(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    # Another device added a tag after this client last read the item.
    crud.update_item_active_tags(
        db.execute("SELECT id FROM items").fetchone()[0], list_id, ["Market"]
    )
    op(client, slug, toggle_body(list_uid, item_uid, "Lidl"))
    assert item_tags(item_uid) == ["Market", "Lidl"]


def test_toggle_on_a_deleted_item_or_another_list(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    gone = add_item(list_id, "milk")
    crud.delete_item(db.execute("SELECT id FROM items").fetchone()[0], list_id)
    other_list_id, _ = crud.create_list("Other", room_id)
    elsewhere = add_item(other_list_id, "bread")
    seq = seq_of(room_id)
    for item_uid in (gone, elsewhere, new_id()):
        response = op(client, slug, toggle_body(list_uid, item_uid, "Lidl"))
        assert response["code"] == "item_not_found"
        assert response["message"] == "The item is no longer available."
    assert item_tags(elsewhere) == []
    assert seq_of(room_id) == seq
    assert notified == []


# list.visibility


def test_visibility_sends_only_changed_fields(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    before = seq_of(room_id)
    response = op(client, slug, list_body("list.visibility", list_uid, mode="age"))
    assert response["status"] == "applied" and response["result"] == {}
    assert feed_list(client, slug, before, list_uid)["hide_done"] == {
        "mode": "age",
        "age_days": 7,
        "recent_count": 10,
    }
    op(client, slug, list_body("list.visibility", list_uid, age_days=3))
    op(
        client,
        slug,
        list_body("list.visibility", list_uid, recent_count=0, mode=None),
    )
    assert visibility(list_id) == ("age", 3, 0)
    assert notified == [room_id] * 3


def test_visibility_merges_with_a_newer_stored_value(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    # Another device changed the mode meanwhile; this one changes a count.
    crud.update_list_visibility_settings(
        list_id, mode="recent", age_days=7, recent_count=10
    )
    op(client, slug, list_body("list.visibility", list_uid, recent_count=4))
    assert visibility(list_id) == ("recent", 7, 4)


def test_visibility_all_fields(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    body = list_body(
        "list.visibility", list_uid, mode="all", age_days=100_000, recent_count=0
    )
    op(client, slug, body)
    assert visibility(list_id) == ("all", 100_000, 0)


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"mode": None, "age_days": None, "recent_count": None},
        {"mode": "bogus"},
        {"mode": ""},
        {"mode": "ALL"},
        {"age_days": -1},
        {"age_days": 100_001},
        {"recent_count": -1},
        {"recent_count": 100_001},
        {"age_days": "7"},
        {"age_days": 7.0},
        {"age_days": True},
        {"mode": "age", "age_days": 2**70},
        {"mode": 1},
        {"hide_done": "all"},
    ],
)
def test_bad_visibility_is_422_and_not_stored(room, fields):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    seq = seq_of(room_id)
    body = list_body("list.visibility", list_uid, **fields)
    assert_error(send(client, slug, body), 422, "invalid_request")
    assert visibility(list_id) == ("off", 7, 10)
    assert seq_of(room_id) == seq
    assert processed_ops_count() == 0
    # Not stored: the same op_id works once the body is fixed.
    body = {"op_id": body["op_id"], "type": "list.visibility", "list_uid": list_uid}
    assert op(client, slug, body | {"mode": "all"})["status"] == "applied"


def test_direct_visibility_still_replaces_all_fields():
    list_id, _ = default_list()
    crud.update_list_visibility_settings(
        list_id, mode="recent", age_days=2, recent_count=3
    )
    assert visibility(list_id) == ("recent", 2, 3)
    with pytest.raises(ValueError):
        crud.update_list_visibility_settings(
            list_id, mode="age", age_days=-1, recent_count=3
        )
    assert visibility(list_id) == ("recent", 2, 3)


# Lists that are gone or in another room

LIST_OPS: dict[str, dict[str, Any]] = {
    "list.tag_add": {"tag": "Lidl"},
    "list.tag_remove": {"tag": "Lidl"},
    "list.visibility": {"mode": "all"},
}


@pytest.mark.parametrize("op_type", [*LIST_OPS, "item.toggle_tag"])
def test_missing_or_foreign_list_is_unavailable(room, notified, op_type):
    room_id, slug, client = room
    other_room_id, _ = crud.create_room("Other", "other-pw")
    other_list_id, _ = crud.create_list("Secret", other_room_id)
    crud.add_list_tag(other_list_id, "Lidl")
    other_item = add_item(other_list_id, "milk")
    other_seq = seq_of(other_room_id)
    seq = seq_of(room_id)
    for list_uid in (new_id(), list_uid_of(other_list_id)):
        fields = LIST_OPS.get(op_type, {"item_uid": other_item, "tag": "Lidl"})
        response = op(client, slug, list_body(op_type, list_uid, **fields))
        assert response["status"] == "rejected"
        assert response["code"] == "list_unavailable"
        assert response["message"] == "The list is no longer available."
    assert stored_tags(other_list_id) == ["Lidl"]
    assert item_tags(other_item) == []
    assert visibility(other_list_id) == ("off", 7, 10)
    assert seq_of(other_room_id) == other_seq
    assert seq_of(room_id) == seq
    assert notified == []


@pytest.mark.parametrize(
    ("op_type", "fields"),
    [
        ("list.tag_add", {}),
        ("list.tag_add", {"tag": None}),
        ("list.tag_add", {"tag": ["Lidl"]}),
        ("list.tag_remove", {"tag": 3}),
        ("item.toggle_tag", {"tag": "Lidl"}),
        ("item.toggle_tag", {"item_uid": "nope", "tag": "Lidl"}),
    ],
)
def test_bad_tag_bodies_are_422(room, op_type, fields):
    _, slug, client = room
    _, list_uid = default_list()
    assert_error(
        send(client, slug, list_body(op_type, list_uid, **fields)),
        422,
        "invalid_request",
    )
    assert processed_ops_count() == 0
