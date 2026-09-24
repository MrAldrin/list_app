"""Item edits save name, description, and quantity together or not at all."""

import pytest

from database_crud import (
    add_item,
    create_list,
    find_item_by_name,
    get_list_data,
    get_rooms,
    update_item_details,
)
from database_setup import db
from item_service import (
    STATUS_DUPLICATE_NAME,
    STATUS_INVALID_NAME,
    STATUS_RENAMED,
    update_item_details_with_checks,
)


@pytest.fixture
def edit_items():
    list_id, slug = create_list("edits", get_rooms()[0]["id"])
    add_item("milk", list_id)
    add_item("bread", list_id)
    item_id = find_item_by_name(list_id, "milk")[0]
    update_item_details(item_id, list_id, "milk", "semi-skimmed", 2)
    return list_id, slug, item_id


def stored_item(list_id, item_id):
    items, _ = get_list_data(list_id)
    item = next(i for i in items if i["id"] == item_id)
    return item["name"], item["description"], item["quantity"]


def test_valid_edit_saves_all_fields(edit_items):
    list_id, slug, item_id = edit_items
    status, name = update_item_details_with_checks(
        list_id, item_id, " Oat Milk ", " barista ", 5, expected_slug=slug
    )
    assert (status, name) == (STATUS_RENAMED, "oat milk")
    assert stored_item(list_id, item_id) == ("oat milk", "barista", 5)
    assert not db.in_transaction


@pytest.mark.parametrize(
    "raw_name, expected_status",
    [("", STATUS_INVALID_NAME), ("   ", STATUS_INVALID_NAME)]
    + [(name, STATUS_DUPLICATE_NAME) for name in ["bread", " BREAD "]],
)
def test_rejected_edit_leaves_every_field_unchanged(
    edit_items, raw_name, expected_status
):
    list_id, slug, item_id = edit_items
    before = stored_item(list_id, item_id)
    status, _ = update_item_details_with_checks(
        list_id, item_id, raw_name, "changed", 9, expected_slug=slug
    )
    assert status == expected_status
    assert stored_item(list_id, item_id) == before == ("milk", "semi-skimmed", 2)
    assert not db.in_transaction


def test_edit_keeps_same_name_with_different_case(edit_items):
    list_id, slug, item_id = edit_items
    status, _ = update_item_details_with_checks(
        list_id, item_id, "MILK", "whole", 3, expected_slug=slug
    )
    assert status == STATUS_RENAMED
    assert stored_item(list_id, item_id) == ("milk", "whole", 3)


def test_duplicate_created_before_save_is_rejected_inside_transaction(edit_items):
    # Another user adds "cheese" after this dialog opened; the save must not
    # rely on an earlier, separate duplicate check.
    list_id, _, item_id = edit_items
    add_item("cheese", list_id)
    assert not update_item_details(item_id, list_id, "cheese", "x", 7)
    assert stored_item(list_id, item_id) == ("milk", "semi-skimmed", 2)
    assert not db.in_transaction


def test_omitted_quantity_is_unchanged(edit_items):
    list_id, _, item_id = edit_items
    assert update_item_details(item_id, list_id, "milk", "note")
    assert stored_item(list_id, item_id) == ("milk", "note", 2)
