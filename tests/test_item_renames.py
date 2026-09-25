"""Item service renames handle competing name claims atomically."""

import pytest

import item_service
from database_crud import (
    ListUnavailable,
    add_item,
    create_list,
    delete_list,
    find_item_by_name,
    get_list_data,
    get_list_details,
    get_rooms,
    update_item_details,
)
from database_setup import db
from item_service import (
    STATUS_DUPLICATE_NAME,
    STATUS_RENAMED,
    rename_item_with_checks,
)


@pytest.fixture
def rename_items():
    list_id, slug = create_list("renames", get_rooms()[0]["id"])
    add_item("milk", list_id)
    item_id = find_item_by_name(list_id, "milk")[0]
    update_item_details(item_id, list_id, "milk", "cold", 4)
    return list_id, slug, item_id


def stored_item(list_id, item_id):
    items, _ = get_list_data(list_id)
    return next(item for item in items if item["id"] == item_id)


def test_normal_rename_preserves_other_fields(rename_items):
    list_id, slug, item_id = rename_items

    status, name = rename_item_with_checks(
        list_id, item_id, " Oat Milk ", expected_slug=slug
    )

    assert (status, name) == (STATUS_RENAMED, "oat milk")
    assert stored_item(list_id, item_id) == {
        "id": item_id,
        "name": "oat milk",
        "done": False,
        "active_tags": [],
        "description": "cold",
        "quantity": 4,
    }
    assert not db.in_transaction


def test_competing_name_claim_returns_duplicate_status(rename_items, monkeypatch):
    list_id, slug, item_id = rename_items
    before = stored_item(list_id, item_id)
    rename_if_unique = item_service.rename_item_if_unique
    claim_once = False

    def competitor_claims_then_rename(**kwargs):
        nonlocal claim_once
        if not claim_once:
            # Let the competing writer commit before this rename's write transaction.
            add_item("claimed", list_id)
            claim_once = True
        return rename_if_unique(**kwargs)

    monkeypatch.setattr(
        item_service, "rename_item_if_unique", competitor_claims_then_rename
    )
    status, name = rename_item_with_checks(
        list_id, item_id, "claimed", expected_slug=slug
    )

    assert (status, name) == (STATUS_DUPLICATE_NAME, "claimed")
    assert stored_item(list_id, item_id) == before
    assert find_item_by_name(list_id, "claimed") is not None
    assert not db.in_transaction

    next_status, next_name = rename_item_with_checks(
        list_id, item_id, "oat milk", expected_slug=slug
    )
    assert (next_status, next_name) == (STATUS_RENAMED, "oat milk")
    assert not db.in_transaction


def test_rename_rejects_reused_list_identity_and_allows_current_identity(
    rename_items,
):
    list_id, old_slug, _ = rename_items
    room_id = get_list_details(list_id)["room_id"]
    delete_list(list_id, expected_slug=old_slug)
    replacement_id, new_slug = create_list("replacement", room_id)
    assert replacement_id == list_id
    add_item("milk", replacement_id)
    add_item("bread", replacement_id)
    new_item_id = find_item_by_name(replacement_id, "milk")[0]
    bread_item_id = find_item_by_name(replacement_id, "bread")[0]

    with pytest.raises(ListUnavailable):
        rename_item_with_checks(
            replacement_id, new_item_id, "bread", expected_slug=old_slug
        )

    assert stored_item(replacement_id, new_item_id)["name"] == "milk"
    assert stored_item(replacement_id, bread_item_id)["name"] == "bread"
    assert not db.in_transaction

    status, name = rename_item_with_checks(
        replacement_id, new_item_id, "oat milk", expected_slug=new_slug
    )
    assert (status, name) == (STATUS_RENAMED, "oat milk")
    assert stored_item(replacement_id, new_item_id)["name"] == "oat milk"
    assert not db.in_transaction
