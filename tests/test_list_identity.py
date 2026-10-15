"""Stale pages must not operate on a replacement list with a reused SQLite ID."""

import pytest
from api_helpers import (
    add_item_with_state,
    create_list,
    find_item_by_name,
    get_list_data,
    get_list_details,
    rotate_list_share_token,
)

import database_crud as crud
from database_setup import db


@pytest.fixture
def room_id():
    return crud.get_rooms()[0]["id"]


@pytest.fixture(params=["reused-id", "revoked-share"])
def replacement(room_id, request):
    list_id, old_slug = create_list("old", room_id)
    if request.param == "revoked-share":
        old_token = get_list_details(list_id)["share_token"]
        new_token = rotate_list_share_token(list_id)
        old_slug, new_slug = f"share:{old_token}", f"share:{new_token}"
    else:
        crud.delete_list(list_id)
        replacement_id, new_slug = create_list("replacement", room_id)
        assert replacement_id == list_id  # Reproduce actual SQLite row-ID reuse.
    add_item_with_state("kept", list_id, True, ["important"])
    item_id = find_item_by_name(list_id, "kept")[0]
    return list_id, old_slug, new_slug, item_id


def snapshot(list_id):
    return get_list_details(list_id), get_list_data(list_id)


@pytest.mark.parametrize(
    "operation, args",
    [
        ("update_item_done", {"done": False}),
        ("update_item_details", {"name": "stale", "description": "stale"}),
        ("update_item_quantity", {"quantity": 99}),
        ("adjust_item_quantity", {"delta": 1}),
        ("delete_item", {}),
        ("delete_list", {}),
    ],
)
def test_database_writes_reject_reused_list_id(replacement, operation, args):
    list_id, old_slug, new_slug, item_id = replacement
    before = snapshot(list_id)
    kwargs = dict(args, list_id=list_id)
    if operation in {
        "update_item_done",
        "update_item_details",
        "update_item_quantity",
        "adjust_item_quantity",
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
