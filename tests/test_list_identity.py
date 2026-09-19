"""Stale pages must not operate on a replacement list with a reused SQLite ID."""

import pytest

import database_crud as crud
import item_service as service
from database_setup import db
from main import _restore_pending_undo


@pytest.fixture
def room_id():
    return crud.get_rooms()[0]["id"]


@pytest.fixture
def replacement(room_id):
    list_id, old_slug = crud.create_list("old", room_id)
    crud.delete_list(list_id)
    replacement_id, new_slug = crud.create_list("replacement", room_id)
    assert replacement_id == list_id  # Reproduce actual SQLite row-ID reuse.
    crud.add_item_with_state("kept", list_id, True, ["important"])
    item_id = crud.find_item_by_name(list_id, "kept")[0]
    return list_id, old_slug, new_slug, item_id


def snapshot(list_id):
    return crud.get_list_details(list_id), crud.get_list_data(list_id)


@pytest.mark.parametrize(
    "operation, args",
    [
        ("add_item", {"item_name": "stale"}),
        (
            "add_item_with_state",
            {"item_name": "stale", "done": False, "active_tags": []},
        ),
        ("restore_item", {}),
        ("update_item_done", {"done": False}),
        ("rename_item", {"new_name": "stale"}),
        ("update_item_details", {"name": "stale", "description": "stale"}),
        ("update_item_quantity", {"quantity": 99}),
        ("adjust_item_quantity", {"delta": 1}),
        ("update_item_active_tags", {"active_tags": ["stale"]}),
        ("delete_item", {}),
        ("update_list_tags_settings", {"list_tags": ["stale"]}),
        ("rename_list", {"new_name": "stale"}),
        ("delete_list", {}),
    ],
)
def test_database_writes_reject_reused_list_id(replacement, operation, args):
    list_id, old_slug, new_slug, item_id = replacement
    before = snapshot(list_id)
    kwargs = dict(args, list_id=list_id)
    if operation in {
        "restore_item",
        "update_item_done",
        "rename_item",
        "update_item_details",
        "update_item_quantity",
        "adjust_item_quantity",
        "update_item_active_tags",
        "delete_item",
    }:
        kwargs["item_id"] = item_id
    mutate = getattr(crud, operation)

    with pytest.raises(crud.ListUnavailable):
        mutate(**kwargs, expected_slug=old_slug)

    assert snapshot(list_id) == before
    assert not db.in_transaction
    # A rejected stale write must not poison the next valid transaction.
    mutate(**kwargs, expected_slug=new_slug)
    assert snapshot(list_id) != before


@pytest.mark.parametrize(
    "operation, args",
    [
        ("add_or_restore_item", {"raw_name": "stale"}),
        ("add_or_restore_item", {"raw_name": "kept"}),
        ("rename_item_with_checks", {"raw_name": "stale"}),
        (
            "update_item_details_with_checks",
            {"raw_name": "stale", "raw_description": "stale"},
        ),
        ("toggle_item_done", {"done": False}),
        ("set_item_quantity", {"quantity": 99}),
        ("change_item_quantity", {"delta": 1}),
        ("delete_item_from_list", {}),
        ("rename_list_with_checks", {"raw_name": "stale"}),
        ("delete_list_and_items", {}),
    ],
)
def test_services_forward_original_slug(replacement, room_id, operation, args):
    list_id, old_slug, _, item_id = replacement
    before = snapshot(list_id)
    kwargs = dict(args, list_id=list_id, expected_slug=old_slug)
    if operation in {"rename_list_with_checks", "delete_list_and_items"}:
        kwargs["room_id"] = room_id
    elif operation != "add_or_restore_item":
        kwargs["item_id"] = item_id

    with pytest.raises(crud.ListUnavailable):
        getattr(service, operation)(**kwargs)

    assert snapshot(list_id) == before
    assert not db.in_transaction


@pytest.mark.parametrize("operation", ["rename", "delete"])
def test_room_token_actions_reject_reused_list_id(replacement, room_id, operation):
    list_id, old_slug, new_slug, _ = replacement
    room = next(r for r in crud.get_rooms() if r["id"] == room_id)
    _, token = crud.authenticate_room_and_issue_token(room["slug"], "pw")
    before = snapshot(list_id)
    kwargs = {"room_slug": room["slug"], "token": token, "list_id": list_id}
    if operation == "rename":
        mutate = crud.rename_list_with_room_token
        kwargs["raw_name"] = "renamed"
    else:
        mutate = crud.delete_list_with_room_token

    with pytest.raises(crud.ListUnavailable):
        mutate(**kwargs, expected_slug=old_slug)
    assert snapshot(list_id) == before
    assert not db.in_transaction
    mutate(**kwargs, expected_slug=new_slug)
    assert snapshot(list_id) != before


@pytest.mark.parametrize("kind", ["item", "tag"])
def test_undo_cannot_restore_into_replacement_list(replacement, kind):
    list_id, old_slug, _, item_id = replacement
    before = snapshot(list_id)
    payload = (
        {"id": item_id, "name": "stale", "done": False, "active_tags": []}
        if kind == "item"
        else {"tag": "stale"}
    )
    pending = {
        "kind": kind,
        "payload": payload,
        "token": "undo-token",
        "message": "undo",
    }
    with pytest.raises(crud.ListUnavailable):
        _restore_pending_undo(list_id, pending, list_slug=old_slug)
    assert snapshot(list_id) == before
