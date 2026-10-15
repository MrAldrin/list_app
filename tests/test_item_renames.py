"""Item renames through the item edit save handle competing name claims."""

import pytest
from api_helpers import (
    create_list,
    find_item_by_name,
    get_list_data,
    insert_item,
    write_locked,
)

from database_crud import get_rooms, update_item_details, update_item_details_locked
from database_setup import db


@pytest.fixture
def rename_items():
    list_id, slug = create_list("renames", get_rooms()[0]["id"])
    insert_item("milk", list_id)
    item_id = find_item_by_name(list_id, "milk")[0]
    update_item_details(item_id, list_id, "milk", "cold", 4)
    return list_id, slug, item_id


def stored_item(list_id, item_id):
    items, _ = get_list_data(list_id)
    return next(item for item in items if item["id"] == item_id)


def test_normal_rename_preserves_other_fields(rename_items):
    list_id, _, item_id = rename_items

    result = write_locked(
        update_item_details_locked, item_id, list_id, "oat milk", "cold", 4
    )

    assert result == "saved"
    assert stored_item(list_id, item_id) == {
        "id": item_id,
        "name": "oat milk",
        "done": False,
        "active_tags": [],
        "description": "cold",
        "quantity": 4,
        "completed_at": None,
    }
    assert not db.in_transaction


def test_competing_name_claim_returns_duplicate_status(rename_items):
    list_id, _, item_id = rename_items
    before = stored_item(list_id, item_id)
    # The competing writer commits its name before this save.
    insert_item("claimed", list_id)

    result = write_locked(
        update_item_details_locked, item_id, list_id, "claimed", "cold", 4
    )

    assert result == "duplicate"
    assert stored_item(list_id, item_id) == before
    assert find_item_by_name(list_id, "claimed") is not None
    assert not db.in_transaction

    assert (
        write_locked(
            update_item_details_locked, item_id, list_id, "oat milk", "cold", 4
        )
        == "saved"
    )
    assert not db.in_transaction
