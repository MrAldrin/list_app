"""Late writes from two devices (docs/api.md, "Writing: operations"; plan 6.1).

A "set" op carries the `base_seq` the page saw. When the row changed after
that and the stored value differs from what the op wants, the op is rejected
with `changed_meanwhile`. Applied answers carry the row's `changed_seq`, so
the device can rebase its own queued ops. Two devices are two sequences of ops
on one client here: the server only sees the ops and their base seqs.
"""

import hashlib
import json
from typing import Any

import pytest
from api_helpers import (
    add_item,
    assert_error,
    create_list,
    default_list,
    item_changed_seq,
    item_row,
    list_changed_seq,
    new_id,
    op,
    send,
)

import database_crud as crud
from api.idempotency import request_hash
from api.ops import parse_op
from database_setup import db


def seq_of(room_id: int) -> int:
    return crud.get_room_seq_locked(room_id)


def body(op_type: str, **fields: Any) -> dict:
    return {"op_id": new_id(), "type": op_type, **fields}


def item(list_uid: str, item_uid: str, op_type: str, **fields: Any) -> dict:
    return body(op_type, list_uid=list_uid, item_uid=item_uid, **fields)


def set_done(list_uid: str, item_uid: str, done: bool, base_seq=None) -> dict:
    fields: dict[str, Any] = {"done": done}
    if base_seq is not None:
        fields["base_seq"] = base_seq
    return item(list_uid, item_uid, "item.set_done", **fields)


def edit(list_uid: str, item_uid: str, base_seq: int, **fields: Any) -> dict:
    fields = {"name": "milk", "description": "", **fields}
    return item(list_uid, item_uid, "item.edit", base_seq=base_seq, **fields)


def done_of(item_uid: str) -> bool:
    return bool(item_row(item_uid)["done"])


def assert_changed_meanwhile(response: dict, room_id: int, seq: int) -> None:
    assert response["status"] == "rejected"
    assert response["code"] == "changed_meanwhile"
    assert response["message"] == "Someone else changed this meanwhile."
    assert response["seq"] == seq == seq_of(room_id)
    assert "result" not in response


@pytest.fixture
def milk(room):
    """(room_id, slug, client, list_uid, milk_uid, base) with an open 'milk'.

    `base` is the milk's changed_seq as the first device saw it.
    """
    room_id, slug, client = room
    list_id, list_uid = default_list()
    milk_uid = add_item(list_id, "milk")
    return room_id, slug, client, list_uid, milk_uid, item_changed_seq(milk_uid)


# set_done


def test_late_tick_after_someone_unticked_is_rejected(milk, notified):
    room_id, slug, client, list_uid, milk_uid, base = milk
    # The other device ticks and unticks; the late tick was made at `base`.
    assert op(client, slug, set_done(list_uid, milk_uid, True))["status"] == "applied"
    assert op(client, slug, set_done(list_uid, milk_uid, False))["status"] == "applied"
    notified.clear()
    late = set_done(list_uid, milk_uid, True, base_seq=base)
    assert_changed_meanwhile(op(client, slug, late), room_id, seq_of(room_id))
    assert not done_of(milk_uid)
    assert notified == []


def test_both_devices_tick_is_applied(milk, notified):
    _room_id, slug, client, list_uid, milk_uid, base = milk
    first = op(client, slug, set_done(list_uid, milk_uid, True, base_seq=base))
    assert first["status"] == "applied"
    stored_at = item_row(milk_uid)["completed_at"]
    # The second device still has `base`; the row already has what it wants.
    second = op(client, slug, set_done(list_uid, milk_uid, True, base_seq=base))
    assert second["status"] == "applied"
    assert second["result"] == {"changed_seq": item_changed_seq(milk_uid)}
    assert done_of(milk_uid)
    assert item_row(milk_uid)["completed_at"] == stored_at


def test_stale_untick_after_someone_ticked_is_rejected(milk):
    room_id, slug, client, list_uid, milk_uid, base = milk
    assert op(client, slug, set_done(list_uid, milk_uid, True))["status"] == "applied"
    late = set_done(list_uid, milk_uid, False, base_seq=base)
    assert_changed_meanwhile(op(client, slug, late), room_id, seq_of(room_id))
    assert done_of(milk_uid)


def test_untick_when_the_row_is_unchanged_is_applied(milk):
    _room_id, slug, client, list_uid, milk_uid, base = milk
    response = op(client, slug, set_done(list_uid, milk_uid, False, base_seq=base))
    assert response["status"] == "applied"
    assert response["result"] == {"changed_seq": item_changed_seq(milk_uid)}


def test_rechecking_a_checked_item_does_not_reject_a_stale_untick(milk):
    room_id, slug, client, list_uid, milk_uid, _base = milk
    assert op(client, slug, set_done(list_uid, milk_uid, True))["status"] == "applied"
    # Page A reads the item now, while it is checked.
    seen = item_changed_seq(milk_uid)
    room_seq = seq_of(room_id)
    # Device B checks it again. Nothing changes, so nothing is stamped.
    assert op(client, slug, set_done(list_uid, milk_uid, True))["status"] == "applied"
    assert item_changed_seq(milk_uid) == seen
    assert seq_of(room_id) == room_seq
    # Page A unticks with the base it saw: applied, not changed_meanwhile.
    response = op(client, slug, set_done(list_uid, milk_uid, False, base_seq=seen))
    assert response["status"] == "applied"
    assert response["result"] == {"changed_seq": item_changed_seq(milk_uid)}
    assert not done_of(milk_uid)


def test_set_done_without_base_seq_is_last_write_wins(milk):
    _room_id, slug, client, list_uid, milk_uid, _base = milk
    op(client, slug, set_done(list_uid, milk_uid, True))
    response = op(client, slug, set_done(list_uid, milk_uid, False))
    assert response["status"] == "applied"
    assert not done_of(milk_uid)


def test_null_base_seq_is_the_same_as_no_base_seq(milk):
    _room_id, slug, client, list_uid, milk_uid, _base = milk
    op(client, slug, set_done(list_uid, milk_uid, True))
    response = op(
        client,
        slug,
        item(list_uid, milk_uid, "item.set_done", done=False, base_seq=None),
    )
    assert response["status"] == "applied"
    assert not done_of(milk_uid)


def test_own_tick_then_untick_with_rebased_base_seq_is_applied(milk):
    _room_id, slug, client, list_uid, milk_uid, base = milk
    tick = op(client, slug, set_done(list_uid, milk_uid, True, base_seq=base))
    assert tick["status"] == "applied"
    # The device moves its next queued op to the seq the tick returned (R3).
    untick = set_done(list_uid, milk_uid, False, base_seq=tick["result"]["changed_seq"])
    response = op(client, slug, untick)
    assert response["status"] == "applied"
    assert response["result"] == {"changed_seq": item_changed_seq(milk_uid)}
    assert not done_of(milk_uid)


def test_own_tick_then_untick_without_rebase_conflicts_with_itself(milk):
    # Why R3 exists: the queued untick still has the old base_seq.
    room_id, slug, client, list_uid, milk_uid, base = milk
    assert (
        op(client, slug, set_done(list_uid, milk_uid, True, base_seq=base))["status"]
        == "applied"
    )
    stale = set_done(list_uid, milk_uid, False, base_seq=base)
    assert_changed_meanwhile(op(client, slug, stale), room_id, seq_of(room_id))


def test_set_done_on_a_deleted_item_is_not_found(milk):
    _room_id, slug, client, list_uid, milk_uid, base = milk
    op(client, slug, item(list_uid, milk_uid, "item.delete"))
    response = op(client, slug, set_done(list_uid, milk_uid, True, base_seq=base))
    assert response["status"] == "rejected"
    assert response["code"] == "item_not_found"


# item.edit


def test_stale_edit_after_someone_renamed_is_rejected(milk, notified):
    room_id, slug, client, list_uid, milk_uid, base = milk
    assert (
        op(client, slug, edit(list_uid, milk_uid, base, name="oat milk"))["status"]
        == "applied"
    )
    notified.clear()
    late = edit(list_uid, milk_uid, base, name="soy milk")
    assert_changed_meanwhile(op(client, slug, late), room_id, seq_of(room_id))
    assert item_row(milk_uid)["name"] == "oat milk"
    assert notified == []


def test_edit_that_wants_the_stored_values_is_applied(milk):
    _room_id, slug, client, list_uid, milk_uid, base = milk
    op(client, slug, edit(list_uid, milk_uid, base, name="oat milk"))
    response = op(client, slug, edit(list_uid, milk_uid, base, name="Oat Milk"))
    assert response["status"] == "applied"
    assert response["result"] == {"changed_seq": item_changed_seq(milk_uid)}


def test_edit_conflicts_when_only_the_description_differs(milk):
    room_id, slug, client, list_uid, milk_uid, base = milk
    op(client, slug, edit(list_uid, milk_uid, base, description="lactose free"))
    late = edit(list_uid, milk_uid, base, name="milk", description="soy")
    assert_changed_meanwhile(op(client, slug, late), room_id, seq_of(room_id))
    assert item_row(milk_uid)["description"] == "lactose free"


def test_edit_does_not_compare_a_quantity_it_did_not_send(milk):
    _room_id, slug, client, list_uid, milk_uid, base = milk
    op(client, slug, item(list_uid, milk_uid, "item.quantity_delta", delta=4))
    response = op(client, slug, edit(list_uid, milk_uid, base))
    assert response["status"] == "applied"
    assert item_row(milk_uid)["quantity"] == 5


def test_edit_conflicts_on_a_quantity_it_sent(milk):
    room_id, slug, client, list_uid, milk_uid, base = milk
    op(client, slug, item(list_uid, milk_uid, "item.quantity_delta", delta=4))
    late = edit(list_uid, milk_uid, base, quantity=2)
    assert_changed_meanwhile(op(client, slug, late), room_id, seq_of(room_id))
    assert item_row(milk_uid)["quantity"] == 5


def test_edit_of_a_deleted_item_is_not_found(milk):
    _room_id, slug, client, list_uid, milk_uid, base = milk
    op(client, slug, item(list_uid, milk_uid, "item.delete"))
    response = op(client, slug, edit(list_uid, milk_uid, base, name="oat milk"))
    assert response["status"] == "rejected"
    assert response["code"] == "item_not_found"
    assert response["message"] == "The item is no longer available."


def test_edit_of_a_deleted_item_is_not_found_whatever_the_base_seq(milk):
    _room_id, slug, client, list_uid, milk_uid, base = milk
    op(client, slug, item(list_uid, milk_uid, "item.delete"))
    response = op(client, slug, edit(list_uid, milk_uid, base + 100))
    assert response["code"] == "item_not_found"


def test_edit_still_needs_a_base_seq(milk):
    _room_id, slug, client, list_uid, milk_uid, _base = milk
    bad = item(list_uid, milk_uid, "item.edit", name="x", description="")
    assert_error(send(client, slug, bad), 422, "invalid_request")


# list.rename


def test_stale_rename_after_someone_renamed_is_rejected(room, notified):
    room_id, slug, client = room
    _, list_uid = default_list()
    base = list_changed_seq(list_uid)
    assert (
        op(
            client,
            slug,
            body("list.rename", list_uid=list_uid, name="Market", base_seq=base),
        )["status"]
        == "applied"
    )
    notified.clear()
    late = body("list.rename", list_uid=list_uid, name="Shop", base_seq=base)
    assert_changed_meanwhile(op(client, slug, late), room_id, seq_of(room_id))
    assert (
        db.execute("SELECT name FROM lists WHERE uid = ?", (list_uid,)).fetchone()[0]
        == "Market"
    )
    assert notified == []


def test_rename_to_the_stored_name_is_applied(room):
    _room_id, slug, client = room
    _, list_uid = default_list()
    base = list_changed_seq(list_uid)
    op(
        client,
        slug,
        body("list.rename", list_uid=list_uid, name="Market", base_seq=base),
    )
    response = op(
        client,
        slug,
        body("list.rename", list_uid=list_uid, name="Market", base_seq=base),
    )
    assert response["status"] == "applied"
    assert response["result"] == {"changed_seq": list_changed_seq(list_uid)}


def test_rename_to_a_taken_name_with_a_current_base_is_a_duplicate(room):
    room_id, slug, client = room
    _, list_uid = default_list()
    create_list("Shop", room_id)
    response = op(
        client,
        slug,
        body(
            "list.rename",
            list_uid=list_uid,
            name="Shop",
            base_seq=list_changed_seq(list_uid),
        ),
    )
    assert response["code"] == "duplicate_name"


# Applied answers carry the row's changed_seq (R3)


def test_one_row_answers_carry_the_new_changed_seq(room):
    _room_id, slug, client = room
    list_id, list_uid = default_list()
    milk_uid = add_item(list_id, "milk")
    bread_uid = add_item(list_id, "bread", done=True)

    def check(response: dict, row_seq: int) -> None:
        assert response["status"] == "applied", response
        assert response["result"]["changed_seq"] == row_seq

    check(
        op(client, slug, set_done(list_uid, milk_uid, True)), item_changed_seq(milk_uid)
    )
    check(
        op(client, slug, item(list_uid, milk_uid, "item.quantity_delta", delta=1)),
        item_changed_seq(milk_uid),
    )
    check(
        op(
            client,
            slug,
            edit(list_uid, milk_uid, item_changed_seq(milk_uid), name="oat"),
        ),
        item_changed_seq(milk_uid),
    )
    check(
        op(client, slug, item(list_uid, milk_uid, "item.toggle_tag", tag="Lidl")),
        item_changed_seq(milk_uid),
    )
    check(
        op(
            client,
            slug,
            body(
                "list.rename",
                list_uid=list_uid,
                name="Shop",
                base_seq=list_changed_seq(list_uid),
            ),
        ),
        list_changed_seq(list_uid),
    )
    check(
        op(client, slug, body("list.tag_add", list_uid=list_uid, tag="Lidl")),
        list_changed_seq(list_uid),
    )
    check(
        op(client, slug, body("list.tag_remove", list_uid=list_uid, tag="Lidl")),
        list_changed_seq(list_uid),
    )
    check(
        op(client, slug, body("list.visibility", list_uid=list_uid, mode="all")),
        list_changed_seq(list_uid),
    )
    # Adding a checked item restores it.
    check(
        op(client, slug, body("item.add", list_uid=list_uid, name="bread")),
        item_changed_seq(bread_uid),
    )
    eggs = op(client, slug, body("item.add", list_uid=list_uid, name="eggs"))
    check(eggs, item_changed_seq(eggs["result"]["item_uid"]))
    deleted = op(client, slug, item(list_uid, bread_uid, "item.delete"))
    assert deleted["result"] == {}
    restored = op(
        client,
        slug,
        body(
            "item.restore",
            list_uid=list_uid,
            name="bread",
            done=False,
            tags=[],
            description="",
            quantity=1,
            completed_at=None,
        ),
    )
    new_uid = restored["result"]["item_uid"]
    check(restored, item_changed_seq(new_uid))


def test_applied_answer_has_the_changed_seq_of_the_stored_row(milk):
    room_id, slug, client, list_uid, milk_uid, base = milk
    response = op(client, slug, set_done(list_uid, milk_uid, True, base_seq=base))
    assert response == {
        "op_id": response["op_id"],
        "status": "applied",
        "result": {"changed_seq": item_changed_seq(milk_uid)},
        "seq": seq_of(room_id),
    }


# item.toggle_tag with active (R4)


def test_toggle_with_active_sets_the_state(milk):
    _room_id, slug, client, list_uid, milk_uid, _base = milk
    on = op(
        client,
        slug,
        item(list_uid, milk_uid, "item.toggle_tag", tag="Lidl", active=True),
    )
    assert on["status"] == "applied"
    assert json.loads(item_row(milk_uid)["tags"]) == ["Lidl"]
    off = op(
        client,
        slug,
        item(list_uid, milk_uid, "item.toggle_tag", tag="Lidl", active=False),
    )
    assert off["status"] == "applied"
    assert json.loads(item_row(milk_uid)["tags"]) == []


def test_toggle_with_active_twice_is_idempotent(milk):
    _room_id, slug, client, list_uid, milk_uid, _base = milk
    first = op(
        client,
        slug,
        item(list_uid, milk_uid, "item.toggle_tag", tag="Lidl", active=True),
    )
    again = op(
        client,
        slug,
        item(list_uid, milk_uid, "item.toggle_tag", tag="Lidl", active=True),
    )
    assert again["status"] == "applied"
    assert (
        again["result"]
        == first["result"]
        == {"changed_seq": item_changed_seq(milk_uid)}
    )
    assert json.loads(item_row(milk_uid)["tags"]) == ["Lidl"]
    # The off state is idempotent too.
    op(
        client,
        slug,
        item(list_uid, milk_uid, "item.toggle_tag", tag="Lidl", active=False),
    )
    again_off = op(
        client,
        slug,
        item(list_uid, milk_uid, "item.toggle_tag", tag="Lidl", active=False),
    )
    assert again_off["status"] == "applied"
    assert json.loads(item_row(milk_uid)["tags"]) == []


def test_toggle_without_active_still_flips(milk):
    _room_id, slug, client, list_uid, milk_uid, _base = milk
    op(client, slug, item(list_uid, milk_uid, "item.toggle_tag", tag="Lidl"))
    op(client, slug, item(list_uid, milk_uid, "item.toggle_tag", tag="Lidl"))
    assert json.loads(item_row(milk_uid)["tags"]) == []


def test_toggle_with_active_must_be_a_bool(milk):
    _room_id, slug, client, list_uid, milk_uid, _base = milk
    for bad in ("true", 1, 0):
        bad_body = item(list_uid, milk_uid, "item.toggle_tag", tag="Lidl", active=bad)
        assert_error(send(client, slug, bad_body), 422, "invalid_request")


# item.add: duplicate names the existing item (R6)


def test_duplicate_add_returns_the_existing_item_uid(milk):
    room_id, slug, client, list_uid, milk_uid, _base = milk
    seq = seq_of(room_id)
    op_id = new_id()
    response = op(
        client,
        slug,
        {"op_id": op_id, "type": "item.add", "list_uid": list_uid, "name": " Milk "},
    )
    assert response == {
        "op_id": op_id,
        "status": "rejected",
        "code": "duplicate_active",
        "message": "'milk' is already on the list",
        "item_uid": milk_uid,
        "seq": seq,
    }


def test_duplicate_add_of_a_new_item_from_another_device(milk):
    _room_id, slug, client, list_uid, _milk_uid, _base = milk
    # Device B adds 'eggs' with its own uid; device A adds 'eggs' too.
    b_uid = new_id()
    assert (
        op(client, slug, body("item.add", list_uid=list_uid, name="eggs", uid=b_uid))[
            "result"
        ]["item_uid"]
        == b_uid
    )
    response = op(
        client, slug, body("item.add", list_uid=list_uid, name="eggs", uid=new_id())
    )
    assert response["code"] == "duplicate_active"
    assert response["item_uid"] == b_uid


# Replay (retry-safe writes)


def test_replay_returns_the_stored_applied_answer(milk, notified):
    _room_id, slug, client, list_uid, milk_uid, base = milk
    request = set_done(list_uid, milk_uid, True, base_seq=base)
    first = send(client, slug, request)
    # The row moves on; the retry must not be re-run against the new state.
    op(client, slug, set_done(list_uid, milk_uid, False))
    calls = list(notified)
    replay = send(client, slug, request)
    assert replay.status_code == 200
    assert replay.content == first.content
    assert notified == calls


def test_replay_returns_the_stored_changed_meanwhile(milk):
    _room_id, slug, client, list_uid, milk_uid, base = milk
    op(client, slug, set_done(list_uid, milk_uid, True))
    op(client, slug, set_done(list_uid, milk_uid, False))
    late = set_done(list_uid, milk_uid, True, base_seq=base)
    first = op(client, slug, late)
    assert first["code"] == "changed_meanwhile"
    # Once the cause is gone (the row now matches), the stored answer stays.
    op(client, slug, set_done(list_uid, milk_uid, True))
    assert op(client, slug, late) == first


def test_replay_of_a_duplicate_add_keeps_the_item_uid(milk):
    _room_id, slug, client, list_uid, milk_uid, _base = milk
    request = body("item.add", list_uid=list_uid, name="milk")
    first = op(client, slug, request)
    assert first["item_uid"] == milk_uid
    assert op(client, slug, request) == first


def test_request_hash_ignores_null_optional_fields_added_later():
    # The hash an op had before base_seq / active existed (their keys absent).
    old_body = {
        "op_id": new_id(),
        "type": "item.set_done",
        "list_uid": new_id(),
        "item_uid": new_id(),
        "done": True,
    }
    old_hash = hashlib.sha256(
        json.dumps(
            old_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    assert request_hash(parse_op(old_body)) == old_hash
    assert request_hash(parse_op({**old_body, "base_seq": None})) == old_hash
    assert request_hash(parse_op({**old_body, "base_seq": 3})) != old_hash

    toggle = {
        "op_id": new_id(),
        "type": "item.toggle_tag",
        "list_uid": new_id(),
        "item_uid": new_id(),
        "tag": "Lidl",
    }
    toggle_hash = hashlib.sha256(
        json.dumps(
            toggle, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    assert request_hash(parse_op(toggle)) == toggle_hash
    assert request_hash(parse_op({**toggle, "active": None})) == toggle_hash
    assert request_hash(parse_op({**toggle, "active": False})) != toggle_hash


def test_op_stored_without_base_seq_replays_when_sent_with_null(milk):
    _room_id, slug, client, list_uid, milk_uid, _base = milk
    request = set_done(list_uid, milk_uid, True)
    first = send(client, slug, request)
    again = send(client, slug, {**request, "base_seq": None})
    assert again.status_code == 200
    assert again.content == first.content
