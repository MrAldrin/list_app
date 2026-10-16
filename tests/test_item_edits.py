"""Item edits save name, description, and quantity together or not at all."""

import pytest
from api_helpers import (
    add_item,
    client_for,
    create_list,
    find_item_by_name,
    home,
    insert_item,
    item_changed_seq,
    item_row,
    list_uid_of,
    new_id,
    op,
    write_locked,
)

from database_crud import update_item_details_locked
from database_setup import db


@pytest.fixture
def edit_items():
    room_id, slug = home()
    list_id, _ = create_list("edits", room_id)
    milk_uid = add_item(list_id, "milk")
    insert_item("bread", list_id)
    write_locked(
        update_item_details_locked,
        find_item_by_name(list_id, "milk")[0],
        list_id,
        "milk",
        "semi-skimmed",
        2,
    )
    return list_id, slug, milk_uid, client_for(slug)


def edit(client, slug, list_id, item_uid, name, description, quantity):
    return op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.edit",
            "list_uid": list_uid_of(list_id),
            "item_uid": item_uid,
            "name": name,
            "description": description,
            "quantity": quantity,
            "base_seq": item_changed_seq(item_uid),
        },
    )


def stored_item(item_uid):
    row = item_row(item_uid)
    return row["name"], row["description"], row["quantity"]


def test_valid_edit_saves_all_fields(edit_items):
    list_id, slug, milk_uid, client = edit_items
    response = edit(client, slug, list_id, milk_uid, " Oat Milk ", " barista ", 5)
    assert response["status"] == "applied"
    assert stored_item(milk_uid) == ("oat milk", "barista", 5)
    assert not db.in_transaction


@pytest.mark.parametrize(
    "raw_name, code",
    [
        ("", "invalid_name"),
        ("   ", "invalid_name"),
        ("bread", "duplicate_name"),
        (" BREAD ", "duplicate_name"),
    ],
)
def test_rejected_edit_leaves_every_field_unchanged(edit_items, raw_name, code):
    list_id, slug, milk_uid, client = edit_items
    response = edit(client, slug, list_id, milk_uid, raw_name, "changed", 9)
    assert (response["status"], response["code"]) == ("rejected", code)
    assert stored_item(milk_uid) == ("milk", "semi-skimmed", 2)
    assert not db.in_transaction


def test_edit_keeps_same_name_with_different_case(edit_items):
    list_id, slug, milk_uid, client = edit_items
    response = edit(client, slug, list_id, milk_uid, "MILK", "whole", 3)
    assert response["status"] == "applied"
    assert stored_item(milk_uid) == ("milk", "whole", 3)


def test_duplicate_created_before_save_is_rejected(edit_items):
    # Another user adds "cheese" after this dialog opened; the save must not
    # rely on an earlier, separate duplicate check.
    list_id, slug, milk_uid, client = edit_items
    insert_item("cheese", list_id)
    response = edit(client, slug, list_id, milk_uid, "cheese", "x", 7)
    assert (response["status"], response["code"]) == ("rejected", "duplicate_name")
    assert stored_item(milk_uid) == ("milk", "semi-skimmed", 2)
    assert not db.in_transaction


def test_omitted_quantity_is_unchanged(edit_items):
    list_id, slug, milk_uid, client = edit_items
    response = edit(client, slug, list_id, milk_uid, "milk", "note", None)
    assert response["status"] == "applied"
    assert stored_item(milk_uid) == ("milk", "note", 2)
