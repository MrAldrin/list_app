"""Names stay unique ignoring case through the API, also beyond A-Z.

SQLite's NOCASE folds only A-Z, so these use Norwegian letters. The rules are
the app's (ARCHITECTURE.md, "Major UX decisions"; tests/test_list_names.py):
list names compare with `casefold`, item names are stored in lowercase. Tags
stay case-sensitive (decision 57).
"""

from typing import Any

import pytest
from api_helpers import (
    add_item,
    client_for,
    default_list,
    home,
    item_row,
    new_id,
    op,
)
from starlette.testclient import TestClient

import database_crud as crud
from database_setup import db


@pytest.fixture
def room() -> tuple[int, str, TestClient]:
    room_id, slug = home()
    return room_id, slug, client_for(slug)


def list_names(room_id: int) -> list[str]:
    rows = db.execute("SELECT name FROM lists WHERE room_id = ?", (room_id,))
    return sorted(row[0] for row in rows)


def list_op(op_type: str, **fields: Any) -> dict[str, Any]:
    return {"op_id": new_id(), "type": op_type, **fields}


@pytest.mark.parametrize("typed", ["ØL", " øl ", "Øl"])
def test_list_create_finds_a_list_in_another_case(room, typed):
    room_id, slug, client = room
    list_id, _ = crud.create_list("øl", room_id)
    before = list_names(room_id)

    result = op(client, slug, list_op("list.create", name=typed, uid=new_id()))

    assert result["status"] == "applied"
    assert result["result"]["created"] is False
    assert result["result"]["list_uid"] == crud.get_list_uid_locked(list_id)
    assert list_names(room_id) == before


def test_list_rename_rejects_another_case_of_another_list(room):
    room_id, slug, client = room
    crud.create_list("Øl", room_id)
    _, list_uid = default_list()

    body = list_op("list.rename", list_uid=list_uid, name=" øL ", base_seq=0)
    result = op(client, slug, body)

    assert result["status"] == "rejected"
    assert result["code"] == "duplicate_name"
    assert "default" in list_names(room_id)


def test_list_rename_to_another_case_of_its_own_name(room):
    room_id, slug, client = room
    list_id, _ = crud.create_list("øl", room_id)
    list_uid = crud.get_list_uid_locked(list_id)

    body = list_op("list.rename", list_uid=list_uid, name="ØL", base_seq=0)

    assert op(client, slug, body)["status"] == "applied"
    assert "ØL" in list_names(room_id)


def test_item_add_finds_an_item_in_another_case(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "øl")

    body = list_op("item.add", list_uid=list_uid, name=" ØL ", uid=new_id())
    result = op(client, slug, body)

    assert result["status"] == "rejected"
    assert result["code"] == "duplicate_active"
    assert item_row(item_uid)["name"] == "øl"


def test_item_add_restores_a_checked_item_in_another_case(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "øl", done=True)

    body = list_op("item.add", list_uid=list_uid, name="Øl", uid=new_id())
    result = op(client, slug, body)

    assert result["status"] == "applied"
    assert result["result"]["outcome"] == "restored"
    assert item_row(item_uid)["done"] == 0


def test_item_edit_rejects_another_case_of_another_item(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    add_item(list_id, "øl")
    other = add_item(list_id, "brus")

    body = list_op(
        "item.edit",
        list_uid=list_uid,
        item_uid=other,
        name="ØL",
        description="",
        base_seq=0,
    )
    result = op(client, slug, body)

    assert result["status"] == "rejected"
    assert result["code"] == "duplicate_name"
    assert item_row(other)["name"] == "brus"


def test_item_restore_rejects_another_case_of_an_existing_item(room):
    _, slug, client = room
    list_id, list_uid = default_list()
    add_item(list_id, "øl")

    body = list_op(
        "item.restore",
        list_uid=list_uid,
        name="ØL",
        done=False,
        tags=[],
        description="",
        quantity=1,
        completed_at=None,
    )
    result = op(client, slug, body)

    assert result["status"] == "rejected"
    assert result["code"] == "undo_name_taken"


def test_tags_stay_case_sensitive(room):
    _, slug, client = room
    _, list_uid = default_list()

    for tag in ("Øl", "øl"):
        body = list_op("list.tag_add", list_uid=list_uid, tag=tag)
        assert op(client, slug, body)["status"] == "applied"

    feed = client.get(f"/api/v1/rooms/{slug}/changes?since=0").json()
    [shared] = [item for item in feed["lists"] if item["uid"] == list_uid]
    assert sorted(shared["tags"]) == ["Øl", "øl"]
