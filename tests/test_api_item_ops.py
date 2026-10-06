"""Item write ops (docs/api.md, "Operation types"; docs/item-writes.md)."""

import json
from datetime import UTC, datetime
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
    """Room IDs passed to live-update listeners (main's listener is replaced)."""
    calls: list[int] = []
    monkeypatch.setattr(live_updates, "_listeners", [calls.append])
    return calls


def seq_of(room_id: int) -> int:
    return crud.get_room_seq_locked(room_id)


def feed_item(client: TestClient, slug: str, since: int, item_uid: str) -> dict:
    """The item as the changes feed sends it after `since`."""
    feed = changes(client, slug, since)
    [item] = [item for item in feed["items"] if item["uid"] == item_uid]
    return item


def item_body(op_type: str, list_uid: str, item_uid: str, **fields: Any) -> dict:
    return {
        "op_id": new_id(),
        "type": op_type,
        "list_uid": list_uid,
        "item_uid": item_uid,
        **fields,
    }


def assert_rejected(
    response: dict, room_id: int, seq: int, code: str, message: str
) -> None:
    assert response["status"] == "rejected"
    assert response["code"] == code
    assert response["message"] == message
    assert response["seq"] == seq == seq_of(room_id)


# item.add


def test_add_item(room, notified):
    room_id, slug, client = room
    _, list_uid = default_list()
    before = seq_of(room_id)
    op_id = new_id()
    response = op(
        client,
        slug,
        {"op_id": op_id, "type": "item.add", "list_uid": list_uid, "name": " Milk "},
    )
    item_uid = response["result"]["item_uid"]
    assert response == {
        "op_id": op_id,
        "status": "applied",
        "result": {"item_uid": item_uid, "outcome": "added"},
        "seq": before + 1,
    }
    assert feed_item(client, slug, before, item_uid) == {
        "uid": item_uid,
        "list_uid": list_uid,
        "name": "milk",
        "done": False,
        "completed_at": None,
        "quantity": 1,
        "description": "",
        "tags": [],
        "changed_seq": before + 1,
    }
    assert notified == [room_id]


def test_add_item_with_client_uid(room):
    _, slug, client = room
    _, list_uid = default_list()
    client_uid = new_id()
    body = {
        "op_id": new_id(),
        "type": "item.add",
        "list_uid": list_uid,
        "name": "milk",
        "uid": client_uid.upper(),
    }
    assert op(client, slug, body)["result"]["item_uid"] == client_uid
    assert item_row(client_uid)["name"] == "milk"


@pytest.mark.parametrize("taken", ["list", "item", "deleted_item"])
def test_add_with_a_used_uid_is_422_and_not_stored(room, taken):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    used = list_uid
    if taken != "list":
        used = add_item(list_id, "old")
    if taken == "deleted_item":
        crud.delete_item(_item_id(used), list_id)
    seq = seq_of(room_id)
    body = {
        "op_id": new_id(),
        "type": "item.add",
        "list_uid": list_uid,
        "name": "milk",
        "uid": used,
    }
    assert_error(send(client, slug, body), 422, "invalid_request")
    assert processed_ops_count() == 0
    assert seq_of(room_id) == seq
    body["uid"] = new_id()
    assert op(client, slug, body)["status"] == "applied"


def _item_id(item_uid: str) -> int:
    return db.execute("SELECT id FROM items WHERE uid = ?", (item_uid,)).fetchone()[0]


def test_add_restores_a_checked_item(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk", done=True)
    assert item_row(item_uid)["completed_at"] is not None
    client_uid = new_id()
    response = op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.add",
            "list_uid": list_uid,
            "name": " MILK ",
            "uid": client_uid,
        },
    )
    assert response["result"] == {"item_uid": item_uid, "outcome": "restored"}
    row = item_row(item_uid)
    assert row["done"] == 0 and row["completed_at"] is None
    assert item_row(client_uid) is None
    assert notified == [room_id]


@pytest.mark.parametrize("name", ["milk", " MILK ", "Milk"])
def test_add_an_active_duplicate_is_rejected(room, notified, name):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_item(list_id, "milk")
    seq = seq_of(room_id)
    response = op(
        client,
        slug,
        {"op_id": new_id(), "type": "item.add", "list_uid": list_uid, "name": name},
    )
    assert_rejected(
        response, room_id, seq, "duplicate_active", "'milk' is already on the list"
    )
    assert db.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1
    assert processed_ops_count() == 1
    assert notified == []


def test_add_with_an_empty_name_is_rejected(room, notified):
    room_id, slug, client = room
    _, list_uid = default_list()
    seq = seq_of(room_id)
    response = op(
        client,
        slug,
        {"op_id": new_id(), "type": "item.add", "list_uid": list_uid, "name": "  "},
    )
    assert_rejected(response, room_id, seq, "invalid_name", "Name cannot be empty")
    assert notified == []


# item.set_done


def test_set_done_and_completed_at(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    before = seq_of(room_id)
    response = op(
        client, slug, item_body("item.set_done", list_uid, item_uid, done=True)
    )
    assert response["status"] == "applied" and response["result"] == {}
    assert response["seq"] == before + 1
    checked = feed_item(client, slug, before, item_uid)
    assert checked["done"] is True
    completed_at = datetime.fromisoformat(checked["completed_at"])
    assert abs((datetime.now(UTC) - completed_at).total_seconds()) < 60

    # Checking again keeps the original time.
    stored = item_row(item_uid)["completed_at"]
    op(client, slug, item_body("item.set_done", list_uid, item_uid, done=True))
    assert item_row(item_uid)["completed_at"] == stored

    # Unchecking clears it.
    before = seq_of(room_id)
    op(client, slug, item_body("item.set_done", list_uid, item_uid, done=False))
    unchecked = feed_item(client, slug, before, item_uid)
    assert unchecked["done"] is False and unchecked["completed_at"] is None
    assert item_row(item_uid)["completed_at"] is None
    assert notified == [room_id] * 3


# item.quantity_delta


def test_quantity_delta(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    before = seq_of(room_id)
    response = op(
        client, slug, item_body("item.quantity_delta", list_uid, item_uid, delta=2)
    )
    assert response["status"] == "applied" and response["result"] == {}
    assert feed_item(client, slug, before, item_uid)["quantity"] == 3
    assert notified == [room_id]


@pytest.mark.parametrize(("start", "delta"), [(3, -10), (1, -1), (None, -5)])
def test_quantity_never_goes_below_one(room, start, delta):
    _, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    db.execute("UPDATE items SET quantity = ? WHERE uid = ?", (start, item_uid))
    db.commit()
    op(client, slug, item_body("item.quantity_delta", list_uid, item_uid, delta=delta))
    assert item_row(item_uid)["quantity"] == 1


def test_empty_quantity_counts_as_one(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    db.execute("UPDATE items SET quantity = NULL WHERE uid = ?", (item_uid,))
    db.commit()
    op(client, slug, item_body("item.quantity_delta", list_uid, item_uid, delta=1))
    assert item_row(item_uid)["quantity"] == 2


# item.edit


def test_edit_saves_all_fields(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    before = seq_of(room_id)
    response = op(
        client,
        slug,
        item_body(
            "item.edit",
            list_uid,
            item_uid,
            name=" Oat Milk ",
            description="  lactose free \n",
            quantity=4,
            base_seq=0,
        ),
    )
    assert response["status"] == "applied" and response["result"] == {}
    item = feed_item(client, slug, before, item_uid)
    assert (item["name"], item["description"], item["quantity"]) == (
        "oat milk",
        "lactose free",
        4,
    )
    assert response["seq"] == before + 1
    assert notified == [room_id]


@pytest.mark.parametrize(("quantity", "saved"), [(None, 3), (0, 1), (-2, 1), (7, 7)])
def test_edit_quantity(room, quantity, saved):
    _, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    crud.update_item_quantity(_item_id(item_uid), list_id, 3)
    fields = {"name": "milk", "description": "", "base_seq": 0}
    if quantity is not None:
        fields["quantity"] = quantity
    op(client, slug, item_body("item.edit", list_uid, item_uid, **fields))
    assert item_row(item_uid)["quantity"] == saved


def test_edit_keeps_the_quantity_when_null(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    crud.update_item_quantity(_item_id(item_uid), list_id, 3)
    body = item_body(
        "item.edit",
        list_uid,
        item_uid,
        name="milk",
        description="x",
        quantity=None,
        base_seq=5,
    )
    op(client, slug, body)
    assert item_row(item_uid)["quantity"] == 3


@pytest.mark.parametrize(
    ("name", "code", "message"),
    [
        ("  ", "invalid_name", "Name cannot be empty"),
        ("bread", "duplicate_name", "'bread' already exists"),
        (" BREAD ", "duplicate_name", "'bread' already exists"),
    ],
)
def test_edit_rejections_change_nothing(room, notified, name, code, message):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    add_item(list_id, "bread")
    before_row = item_row(item_uid)
    seq = seq_of(room_id)
    body = item_body(
        "item.edit",
        list_uid,
        item_uid,
        name=name,
        description="new",
        quantity=9,
        base_seq=0,
    )
    assert_rejected(op(client, slug, body), room_id, seq, code, message)
    assert item_row(item_uid) == before_row
    assert notified == []


def test_edit_to_its_own_name(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    body = item_body(
        "item.edit", list_uid, item_uid, name="MILK", description="d", base_seq=0
    )
    assert op(client, slug, body)["status"] == "applied"
    assert item_row(item_uid)["description"] == "d"


@pytest.mark.parametrize(
    "extra", [{}, {"base_seq": None}, {"base_seq": -1}, {"base_seq": "1"}]
)
def test_edit_needs_a_base_seq(room, extra):
    _, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    body = item_body("item.edit", list_uid, item_uid, name="x", description="", **extra)
    assert_error(send(client, slug, body), 422, "invalid_request")


# item.delete


def test_delete_item(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    before = seq_of(room_id)
    response = op(client, slug, item_body("item.delete", list_uid, item_uid))
    assert response["status"] == "applied" and response["result"] == {}
    assert item_row(item_uid) is None
    feed = changes(client, slug, before)
    assert feed["seq"] == response["seq"] == before + 1
    assert feed["deletions"] == [{"kind": "item", "uid": item_uid}]
    assert notified == [room_id]


def test_delete_of_a_gone_item_is_applied(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    op(client, slug, item_body("item.delete", list_uid, item_uid))
    seq = seq_of(room_id)
    again = op(client, slug, item_body("item.delete", list_uid, item_uid))
    assert again["status"] == "applied"
    assert again["seq"] == seq == seq_of(room_id)
    never = op(client, slug, item_body("item.delete", list_uid, new_id()))
    assert never["status"] == "applied"
    assert notified == [room_id] * 3


def test_delete_does_not_touch_an_item_of_another_list(room):
    room_id, slug, client = room
    _, list_uid = default_list()
    other_list_id, _ = crud.create_list("Other", room_id)
    other_item = add_item(other_list_id, "milk")
    seq = seq_of(room_id)
    response = op(client, slug, item_body("item.delete", list_uid, other_item))
    assert response["status"] == "applied"
    assert item_row(other_item) is not None
    assert seq_of(room_id) == seq


# item.restore


def restore_body(list_uid: str, **fields: Any) -> dict:
    return {
        "op_id": new_id(),
        "type": "item.restore",
        "list_uid": list_uid,
        "name": "milk",
        "done": True,
        "tags": ["Lidl", "Market"],
        "description": "lactose free",
        "quantity": 2,
        "completed_at": "2026-10-03T09:12:44.123456Z",
        **fields,
    }


def test_restore_creates_a_new_item(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    old_uid = add_item(list_id, "milk")
    op(client, slug, item_body("item.delete", list_uid, old_uid))
    before = seq_of(room_id)
    response = op(client, slug, restore_body(list_uid))
    assert response["status"] == "applied"
    new_uid = response["result"]["item_uid"]
    assert response["result"] == {"item_uid": new_uid}
    assert new_uid != old_uid
    assert feed_item(client, slug, before, new_uid) == {
        "uid": new_uid,
        "list_uid": list_uid,
        "name": "milk",
        "done": True,
        "completed_at": "2026-10-03T09:12:44.123456Z",
        "quantity": 2,
        "description": "lactose free",
        "tags": ["Lidl", "Market"],
        "changed_seq": before + 1,
    }
    assert notified == [room_id, room_id]


def test_restore_with_client_uid_and_normalized_values(room):
    _, slug, client = room
    _, list_uid = default_list()
    client_uid = new_id()
    body = restore_body(
        list_uid,
        uid=client_uid,
        name=" MILK ",
        completed_at="2026-10-03T11:12:44+02:00",
        quantity=0,
    )
    assert op(client, slug, body)["result"] == {"item_uid": client_uid}
    row = item_row(client_uid)
    assert row["name"] == "milk"
    assert row["completed_at"] == "2026-10-03T09:12:44.000000Z"
    assert row["quantity"] == 1
    assert json.loads(row["tags"]) == ["Lidl", "Market"]


def test_restore_keeps_completed_at_only_when_done(room):
    _, slug, client = room
    _, list_uid = default_list()
    response = op(client, slug, restore_body(list_uid, done=False))
    row = item_row(response["result"]["item_uid"])
    assert row["done"] == 0 and row["completed_at"] is None


def test_restore_without_a_known_completion_time(room):
    _, slug, client = room
    _, list_uid = default_list()
    response = op(client, slug, restore_body(list_uid, completed_at=None))
    row = item_row(response["result"]["item_uid"])
    assert row["done"] == 1 and row["completed_at"] is None


@pytest.mark.parametrize("name", ["milk", " Milk "])
def test_restore_when_the_name_is_taken(room, notified, name):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_item(list_id, "milk", done=True)
    seq = seq_of(room_id)
    client_uid = new_id()
    response = op(client, slug, restore_body(list_uid, name=name, uid=client_uid))
    assert_rejected(
        response,
        room_id,
        seq,
        "undo_name_taken",
        "Cannot undo: item name already exists",
    )
    assert db.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1
    assert item_row(client_uid) is None
    assert notified == []


def test_restore_with_an_empty_name_is_rejected(room):
    room_id, slug, client = room
    _, list_uid = default_list()
    seq = seq_of(room_id)
    response = op(client, slug, restore_body(list_uid, name=" "))
    assert_rejected(response, room_id, seq, "invalid_name", "Name cannot be empty")


def test_restore_with_a_used_uid_is_422(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    used = add_item(list_id, "bread")
    body = restore_body(list_uid, uid=used)
    assert_error(send(client, slug, body), 422, "invalid_request")
    assert processed_ops_count() == 0


# Stale items and other lists


ITEM_OPS: dict[str, dict[str, Any]] = {
    "item.set_done": {"done": True},
    "item.quantity_delta": {"delta": 1},
    "item.edit": {"name": "new", "description": "", "base_seq": 0},
}


@pytest.mark.parametrize("op_type", ITEM_OPS)
def test_deleted_item_is_not_found(room, notified, op_type):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    crud.delete_item(_item_id(item_uid), list_id)
    seq = seq_of(room_id)
    response = op(
        client, slug, item_body(op_type, list_uid, item_uid, **ITEM_OPS[op_type])
    )
    assert_rejected(
        response, room_id, seq, "item_not_found", "The item is no longer available."
    )
    assert db.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
    assert notified == []


@pytest.mark.parametrize("op_type", ITEM_OPS)
def test_item_of_another_list_is_not_found(room, op_type):
    room_id, slug, client = room
    _, list_uid = default_list()
    other_list_id, _ = crud.create_list("Other", room_id)
    other_item = add_item(other_list_id, "milk")
    before_row = item_row(other_item)
    seq = seq_of(room_id)
    response = op(
        client, slug, item_body(op_type, list_uid, other_item, **ITEM_OPS[op_type])
    )
    assert_rejected(
        response, room_id, seq, "item_not_found", "The item is no longer available."
    )
    assert item_row(other_item) == before_row


@pytest.mark.parametrize("op_type", [*ITEM_OPS, "item.delete"])
def test_item_of_another_room(room, op_type):
    _, slug, client = room
    _, list_uid = default_list()
    other_room_id, _ = crud.create_room("Other", "other-pw")
    other_list_id, _ = crud.create_list("Secret", other_room_id)
    other_list_uid = list_uid_of(other_list_id)
    other_item = add_item(other_list_id, "milk")
    before_row = item_row(other_item)
    other_seq = seq_of(other_room_id)
    fields = ITEM_OPS.get(op_type, {})
    # Through our own list: the item is not in it.
    via_own = op(client, slug, item_body(op_type, list_uid, other_item, **fields))
    expected = "applied" if op_type == "item.delete" else "rejected"
    assert via_own["status"] == expected
    # Naming the other room's list: unavailable.
    via_other = op(
        client, slug, item_body(op_type, other_list_uid, other_item, **fields)
    )
    assert via_other["code"] == "list_unavailable"
    assert item_row(other_item) == before_row
    assert seq_of(other_room_id) == other_seq


def _all_item_bodies(list_uid: str, item_uid: str) -> list[dict]:
    return [
        {
            "op_id": new_id(),
            "type": "item.add",
            "list_uid": list_uid,
            "name": "milk",
        },
        *(item_body(t, list_uid, item_uid, **f) for t, f in ITEM_OPS.items()),
        item_body("item.delete", list_uid, item_uid),
        restore_body(list_uid),
    ]


def test_every_item_op_on_a_missing_list_is_unavailable(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    crud.delete_list(list_id)
    seq = seq_of(room_id)
    for body in _all_item_bodies(list_uid, item_uid):
        assert_rejected(
            op(client, slug, body),
            room_id,
            seq,
            "list_unavailable",
            "The list is no longer available.",
        )
    assert notified == []


# Request rules


@pytest.mark.parametrize(
    ("op_type", "fields"),
    [
        ("item.add", {"name": 5}),
        ("item.add", {"name": "x", "uid": "nope"}),
        ("item.set_done", {"done": "true"}),
        ("item.set_done", {"done": 1}),
        ("item.set_done", {}),
        ("item.quantity_delta", {"delta": "1"}),
        ("item.quantity_delta", {"delta": 1.5}),
        ("item.quantity_delta", {"delta": True}),
        ("item.quantity_delta", {"delta": 1_000_001}),
        ("item.quantity_delta", {"delta": 2**70}),
        ("item.edit", {"name": "x", "base_seq": 0}),
        (
            "item.edit",
            {"name": "x", "description": "", "quantity": 10**7, "base_seq": 0},
        ),
        ("item.delete", {"extra": 1}),
        ("item.restore", {"tags": "Lidl"}),
        ("item.restore", {"tags": [1]}),
        ("item.restore", {"completed_at": "yesterday"}),
        ("item.restore", {"quantity": "2"}),
        ("item.restore", {"done": None}),
    ],
)
def test_bad_item_bodies_are_422(room, op_type, fields):
    _, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    if op_type == "item.restore":
        body = restore_body(list_uid, **fields)
    elif op_type == "item.add":
        body = {"op_id": new_id(), "type": op_type, "list_uid": list_uid, **fields}
    else:
        body = item_body(op_type, list_uid, item_uid, **fields)
    assert_error(send(client, slug, body), 422, "invalid_request")
    assert processed_ops_count() == 0


def test_restore_needs_completed_at(room):
    _, slug, client = room
    _, list_uid = default_list()
    body = restore_body(list_uid)
    del body["completed_at"]
    assert_error(send(client, slug, body), 422, "invalid_request")


def test_item_ops_need_room_access(room):
    room_id, slug, _ = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    seq = seq_of(room_id)
    stranger = client_for()
    for body in _all_item_bodies(list_uid, item_uid):
        assert_error(send(stranger, slug, body), 401, "not_authenticated")
    assert seq_of(room_id) == seq
    assert processed_ops_count() == 0


# The database helpers keep their silent no-op on stale items, through the same helpers.


def test_database_helpers_stay_silent_on_a_stale_item():
    list_id, _ = default_list()
    item_uid = add_item(list_id, "milk")
    item_id = _item_id(item_uid)
    crud.delete_item(item_id, list_id)
    crud.update_item_done(item_id, list_id, True)
    crud.adjust_item_quantity(item_id, list_id, 1)
    assert crud.update_item_details(item_id, list_id, "x", "") is True
    crud.delete_item(item_id, list_id)
    assert db.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0


def test_locked_helpers_report_a_stale_item():
    list_id, _ = default_list()
    item_uid = add_item(list_id, "milk")
    item_id = _item_id(item_uid)
    crud.delete_item(item_id, list_id)
    with _transaction():
        assert crud.update_item_done_locked(item_id, list_id, True) is False
        assert crud.adjust_item_quantity_locked(item_id, list_id, 1) is False
        assert crud.delete_item_locked(item_id, list_id) is False
        assert (
            crud.update_item_details_locked(item_id, list_id, "x", "", None)
            == "missing"
        )


class _transaction:
    def __enter__(self) -> None:
        db.execute("BEGIN IMMEDIATE")

    def __exit__(self, *exc: object) -> None:
        db.rollback()
