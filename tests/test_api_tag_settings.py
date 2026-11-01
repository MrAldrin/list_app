"""Tag settings ops: mode, tag display, colors and rename (docs/api-lists-items.md)."""

import json
from typing import Any

import pytest
from api_helpers import (
    add_item,
    add_list_tag,
    assert_error,
    changes,
    client_for,
    create_list,
    default_list,
    home,
    item_changed_seq,
    item_row,
    list_changed_seq,
    list_uid_of,
    new_id,
    op,
    processed_ops_count,
    row_counts,
    send,
    toggle_item_active_tag,
    update_item_active_tags,
)
from starlette.testclient import TestClient

import api.ops as api_ops
import database_crud as crud
from database_setup import db


def seq_of(room_id: int) -> int:
    return crud.get_room_seq_locked(room_id)


def list_body(op_type: str, list_uid: str, **fields: Any) -> dict:
    return {"op_id": new_id(), "type": op_type, "list_uid": list_uid, **fields}


def item_id_of(item_uid: str) -> int:
    return db.execute("SELECT id FROM items WHERE uid = ?", (item_uid,)).fetchone()[0]


def stored_tags(list_id: int) -> list[str]:
    return json.loads(
        db.execute("SELECT list_tags FROM lists WHERE id = ?", (list_id,)).fetchone()[0]
    )


def stored_colors(list_id: int) -> dict[str, int]:
    return json.loads(
        db.execute("SELECT tag_colors FROM lists WHERE id = ?", (list_id,)).fetchone()[
            0
        ]
    )


def item_tags(item_uid: str) -> list[str]:
    return json.loads(item_row(item_uid)["tags"] or "[]")


def settings(client: TestClient, slug: str, list_uid: str) -> dict:
    [found] = [
        row for row in changes(client, slug, 0)["lists"] if row["uid"] == list_uid
    ]
    return found["tag_settings"]


def settings_body(list_uid: str, **fields: Any) -> dict:
    return list_body("list.tag_settings", list_uid, **fields)


def color_body(list_uid: str, tag: str, color: int | None) -> dict:
    return list_body("list.tag_color", list_uid, tag=tag, color=color)


def rename_body(list_uid: str, tag: str, new_tag: str) -> dict:
    return list_body("list.tag_rename", list_uid, tag=tag, new_tag=new_tag)


# list.tag_settings


def test_tag_settings_merges_only_the_sent_fields(room, notified):
    room_id, slug, client = room
    _, list_uid = default_list()
    before = seq_of(room_id)
    response = op(client, slug, settings_body(list_uid, mode="single"))
    assert response["status"] == "applied"
    assert response["result"] == {"changed_seq": list_changed_seq(list_uid)}
    assert response["seq"] == before + 1
    assert settings(client, slug, list_uid) == {
        "mode": "single",
        "show_on_items": True,
        "only_item_tags": False,
        "colors": {},
    }
    op(client, slug, settings_body(list_uid, only_item_tags=True))
    assert settings(client, slug, list_uid) == {
        "mode": "single",
        "show_on_items": True,
        "only_item_tags": True,
        "colors": {},
    }
    assert notified == [room_id] * 2


def test_tag_settings_without_a_change_writes_nothing(room, notified):
    room_id, slug, client = room
    _, list_uid = default_list()
    seq = seq_of(room_id)
    response = op(client, slug, settings_body(list_uid, show_on_items=True))
    assert response["status"] == "applied"
    assert response["seq"] == seq == seq_of(room_id)
    assert notified == [room_id]


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"mode": "many"},
        {"mode": None},
        {"show_on_items": "yes"},
        {"show_on_items": 1},
        {"only_item_tags": 0},
    ],
)
def test_bad_tag_settings_are_422_and_not_stored(room, notified, fields):
    room_id, slug, client = room
    _, list_uid = default_list()
    seq = seq_of(room_id)
    assert_error(
        send(client, slug, settings_body(list_uid, **fields)), 422, "invalid_request"
    )
    assert processed_ops_count() == 0
    assert seq_of(room_id) == seq
    assert notified == []


def test_tag_settings_on_a_missing_list_is_unavailable(room, notified):
    _, slug, client = room
    response = op(client, slug, settings_body(new_id(), mode="single"))
    assert response["status"] == "rejected"
    assert response["code"] == "list_unavailable"
    assert notified == []


def test_switching_to_single_keeps_the_first_tag_in_list_order(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    for tag in ["Market", "Lidl", "aldi"]:
        add_list_tag(list_id, tag)  # the list order is aldi, Lidl, Market
    first = add_item(list_id, "milk")
    second = add_item(list_id, "bread")
    unknown = add_item(list_id, "eggs")
    update_item_active_tags(item_id_of(first), list_id, ["Market", "Lidl", "aldi"])
    update_item_active_tags(item_id_of(second), list_id, ["Lidl", "Market"])
    update_item_active_tags(item_id_of(unknown), list_id, ["gone", "Market"])
    before = seq_of(room_id)
    response = op(client, slug, settings_body(list_uid, mode="single"))
    assert response["status"] == "applied"
    assert response["seq"] == seq_of(room_id) > before
    assert item_tags(first) == ["aldi"]
    assert item_tags(second) == ["Lidl"]
    # A tag the list no longer has ranks after the list's tags.
    assert item_tags(unknown) == ["Market"]
    changed = {i["uid"] for i in changes(client, slug, before)["items"]}
    assert changed == {first, second, unknown}
    assert notified == [room_id]


def test_switching_to_single_keeps_single_tag_items_untouched(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    item = add_item(list_id, "milk")
    update_item_active_tags(item_id_of(item), list_id, ["Lidl"])
    seq = item_changed_seq(item)
    op(client, slug, settings_body(list_uid, mode="single"))
    assert item_tags(item) == ["Lidl"]
    assert item_changed_seq(item) == seq


def test_toggle_in_single_mode_keeps_only_the_tag_turned_on(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    add_list_tag(list_id, "Market")
    item = add_item(list_id, "milk")
    op(client, slug, settings_body(list_uid, mode="single"))
    op(
        client,
        slug,
        list_body("item.toggle_tag", list_uid, item_uid=item, tag="Lidl"),
    )
    op(
        client,
        slug,
        list_body("item.toggle_tag", list_uid, item_uid=item, tag="Market"),
    )
    assert item_tags(item) == ["Market"]
    op(
        client,
        slug,
        list_body(
            "item.toggle_tag", list_uid, item_uid=item, tag="Market", active=False
        ),
    )
    assert item_tags(item) == []


def test_toggle_on_in_single_mode_with_active_true_replaces_other_tags(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    add_list_tag(list_id, "Market")
    item = add_item(list_id, "milk")
    update_item_active_tags(item_id_of(item), list_id, ["Lidl"])
    op(client, slug, settings_body(list_uid, mode="single"))
    response = op(
        client,
        slug,
        list_body(
            "item.toggle_tag", list_uid, item_uid=item, tag="Market", active=True
        ),
    )
    assert response["status"] == "applied"
    assert item_tags(item) == ["Market"]


# list.tag_color


def test_tag_color_sets_and_clears_one_tags_color(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    add_list_tag(list_id, "Market")
    before = seq_of(room_id)
    response = op(client, slug, color_body(list_uid, "Lidl", 3))
    assert response["status"] == "applied"
    assert response["result"] == {"changed_seq": list_changed_seq(list_uid)}
    assert response["seq"] == before + 1
    assert settings(client, slug, list_uid)["colors"] == {"Lidl": 3}
    assert stored_colors(list_id) == {"Lidl": 3}
    op(client, slug, color_body(list_uid, "Market", 6))
    assert stored_colors(list_id) == {"Lidl": 3, "Market": 6}
    op(client, slug, color_body(list_uid, "Lidl", None))
    assert stored_colors(list_id) == {"Market": 6}
    assert notified == [room_id] * 3


def test_same_tag_color_writes_nothing(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    op(client, slug, color_body(list_uid, "Lidl", 2))
    seq = seq_of(room_id)
    response = op(client, slug, color_body(list_uid, "Lidl", 2))
    assert response["status"] == "applied"
    assert response["seq"] == seq == seq_of(room_id)
    assert notified == [room_id] * 2


def test_clearing_a_color_that_is_not_set_writes_nothing(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    seq = seq_of(room_id)
    response = op(client, slug, color_body(list_uid, "Lidl", None))
    assert response["status"] == "applied"
    assert seq_of(room_id) == seq
    assert notified == [room_id]


@pytest.mark.parametrize("color", [-1, 7, "red", True, 1.5])
def test_bad_tag_color_is_422_and_not_stored(room, notified, color):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    seq = seq_of(room_id)
    assert_error(
        send(client, slug, color_body(list_uid, "Lidl", color)),
        422,
        "invalid_request",
    )
    assert stored_colors(list_id) == {}
    assert seq_of(room_id) == seq
    assert notified == []


def test_tag_color_of_an_unknown_tag_is_rejected(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    seq = seq_of(room_id)
    response = op(client, slug, color_body(list_uid, "Nope", 2))
    assert response["status"] == "rejected"
    assert response["code"] == "unknown_tag"
    assert response["message"] == "The tag is not on this list."
    assert response["seq"] == seq
    assert stored_colors(list_id) == {}
    assert notified == []


def test_tag_color_match_is_exact(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    response = op(client, slug, color_body(list_uid, "lidl", 2))
    assert response["code"] == "unknown_tag"


def test_removing_a_tag_drops_its_color(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    add_list_tag(list_id, "Market")
    op(client, slug, color_body(list_uid, "Lidl", 4))
    op(client, slug, color_body(list_uid, "Market", 1))
    op(client, slug, list_body("list.tag_remove", list_uid, tag="Lidl"))
    assert stored_colors(list_id) == {"Market": 1}
    assert settings(client, slug, list_uid)["colors"] == {"Market": 1}


# list.tag_rename


def test_rename_changes_the_list_items_and_color_together(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    add_list_tag(list_id, "Market")
    op(client, slug, color_body(list_uid, "Lidl", 2))
    first = add_item(list_id, "milk")
    second = add_item(list_id, "bread")
    third = add_item(list_id, "eggs")
    update_item_active_tags(item_id_of(first), list_id, ["Market", "Lidl"])
    update_item_active_tags(item_id_of(second), list_id, ["Lidl"])
    update_item_active_tags(item_id_of(third), list_id, ["Market"])
    before = seq_of(room_id)
    response = op(client, slug, rename_body(list_uid, "Lidl", "Aldi"))
    assert response["status"] == "applied"
    assert response["result"] == {"changed_seq": list_changed_seq(list_uid)}
    assert response["seq"] == seq_of(room_id) > before
    assert stored_tags(list_id) == ["Aldi", "Market"]
    assert stored_colors(list_id) == {"Aldi": 2}
    assert item_tags(first) == ["Market", "Aldi"]  # same position
    assert item_tags(second) == ["Aldi"]
    assert item_tags(third) == ["Market"]
    assert settings(client, slug, list_uid)["colors"] == {"Aldi": 2}
    assert notified == [room_id, room_id]  # the color op, then the rename


def test_rename_resorts_the_list_tags(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    for tag in ["beta", "Gamma"]:
        add_list_tag(list_id, tag)
    op(client, slug, rename_body(list_uid, "Gamma", "alpha"))
    assert stored_tags(list_id) == ["alpha", "beta"]


def test_rename_trims_the_new_name(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    response = op(client, slug, rename_body(list_uid, "Lidl", "  Aldi  "))
    assert response["status"] == "applied"
    assert stored_tags(list_id) == ["Aldi"]


def test_rename_does_not_duplicate_an_item_tag(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    item = add_item(list_id, "milk")
    # Stored tags that the list does not have yet: renaming gives a duplicate.
    update_item_active_tags(item_id_of(item), list_id, ["Lidl", "Aldi"])
    op(client, slug, rename_body(list_uid, "Lidl", "Aldi"))
    assert item_tags(item) == ["Aldi"]


def test_renaming_a_tag_to_its_own_name_writes_nothing(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    seq = seq_of(room_id)
    response = op(client, slug, rename_body(list_uid, "Lidl", "Lidl"))
    assert response["status"] == "applied"
    assert response["seq"] == seq == seq_of(room_id)
    assert notified == [room_id]


@pytest.mark.parametrize(
    ("tag", "new_tag", "code", "message"),
    [
        ("Lidl", "Market", "duplicate_name", "'Market' already exists"),
        ("Nope", "Aldi", "unknown_tag", "The tag is not on this list."),
        ("Lidl", "   ", "invalid_name", "Name cannot be empty"),
        ("Lidl", "x" * 31, "too_long", "Tag can be at most 30 characters"),
    ],
)
def test_rename_rejections_change_nothing(room, notified, tag, new_tag, code, message):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    add_list_tag(list_id, "Market")
    op(client, slug, color_body(list_uid, "Lidl", 5))
    item = add_item(list_id, "milk")
    update_item_active_tags(item_id_of(item), list_id, ["Lidl"])
    seq = seq_of(room_id)
    notified.clear()
    response = op(client, slug, rename_body(list_uid, tag, new_tag))
    assert response["status"] == "rejected"
    assert response["code"] == code
    assert response["message"] == message
    assert response["seq"] == seq == seq_of(room_id)
    assert stored_tags(list_id) == ["Lidl", "Market"]
    assert stored_colors(list_id) == {"Lidl": 5}
    assert item_tags(item) == ["Lidl"]
    assert notified == []


def test_rename_is_atomic_when_a_later_step_fails(room, monkeypatch):
    _, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    op(client, slug, color_body(list_uid, "Lidl", 5))
    item = add_item(list_id, "milk")
    update_item_active_tags(item_id_of(item), list_id, ["Lidl"])
    before_rows = row_counts()
    before_ops = processed_ops_count()

    def broken(list_id: int) -> int:
        raise RuntimeError("simulated failure after the rename")

    monkeypatch.setattr(api_ops, "get_list_changed_seq_locked", broken)
    response = send(client, slug, rename_body(list_uid, "Lidl", "Aldi"))
    assert response.status_code == 500
    assert stored_tags(list_id) == ["Lidl"]
    assert stored_colors(list_id) == {"Lidl": 5}
    assert item_tags(item) == ["Lidl"]
    assert row_counts() == before_rows
    assert processed_ops_count() == before_ops


def test_rename_replay_returns_the_stored_answer(room, notified):
    room_id, slug, client = room
    list_id, list_uid = default_list()
    add_list_tag(list_id, "Lidl")
    body = rename_body(list_uid, "Lidl", "Aldi")
    first = op(client, slug, body)
    seq = seq_of(room_id)
    second = op(client, slug, body)
    assert second == first
    assert seq_of(room_id) == seq
    assert stored_tags(list_id) == ["Aldi"]
    assert notified == [room_id]


# Share links: the list's tag settings, colors and rename, never another list.


@pytest.fixture
def shared_list():
    room_id, _ = home()
    list_id, _ = create_list("Groceries", room_id)
    add_list_tag(list_id, "Lidl")
    other_id, _ = create_list("Private", room_id)
    add_list_tag(other_id, "Secret")
    token = db.execute(
        "SELECT share_token FROM lists WHERE id = ?", (list_id,)
    ).fetchone()[0]
    return {
        "room_id": room_id,
        "list_id": list_id,
        "list_uid": list_uid_of(list_id),
        "other_id": other_id,
        "other_uid": list_uid_of(other_id),
        "token": token,
    }


def share_send(token: str, body: dict) -> dict:
    response = client_for().post(f"/api/v1/share/{token}/ops", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_share_link_can_change_its_lists_tag_settings(shared_list):
    token = shared_list["token"]
    settled = share_send(
        token, list_body("list.tag_settings", shared_list["list_uid"], mode="single")
    )
    assert settled["status"] == "applied"
    colored = share_send(
        token, list_body("list.tag_color", shared_list["list_uid"], tag="Lidl", color=1)
    )
    assert colored["status"] == "applied"
    renamed = share_send(token, rename_body(shared_list["list_uid"], "Lidl", "Aldi"))
    assert renamed["status"] == "applied"
    assert stored_tags(shared_list["list_id"]) == ["Aldi"]
    assert stored_colors(shared_list["list_id"]) == {"Aldi": 1}


def test_share_link_reaches_no_other_list(shared_list):
    token = shared_list["token"]
    other = shared_list["other_uid"]
    for body in (
        list_body("list.tag_settings", other, mode="single"),
        list_body("list.tag_color", other, tag="Secret", color=2),
        rename_body(other, "Secret", "Open"),
    ):
        response = share_send(token, body)
        assert response["status"] == "rejected"
        assert response["code"] == "list_unavailable"
    assert stored_tags(shared_list["other_id"]) == ["Secret"]
    assert stored_colors(shared_list["other_id"]) == {}


def test_settings_replay_with_another_body_is_409(room):
    _, slug, client = room
    _, list_uid = default_list()
    body = settings_body(list_uid, mode="single")
    op(client, slug, body)
    response = send(client, slug, {**body, "mode": "multi"})
    assert_error(response, 409, "op_id_reused")


def test_tag_settings_are_in_the_list_feed_for_every_device(room):
    _, slug, client = room
    _, list_uid = default_list()
    op(client, slug, settings_body(list_uid, mode="single", show_on_items=False))
    other_device = client_for(slug)
    assert settings(other_device, slug, list_uid) == {
        "mode": "single",
        "show_on_items": False,
        "only_item_tags": False,
        "colors": {},
    }


def test_item_writes_do_not_change_tag_settings(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    op(client, slug, settings_body(list_uid, mode="single"))
    before = settings(client, slug, list_uid)
    item = add_item(list_id, "milk")
    toggle_item_active_tag(item_id_of(item), list_id, "Lidl")
    assert settings(client, slug, list_uid) == before
