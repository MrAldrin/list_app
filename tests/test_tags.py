"""Regression tests for list tags and per-item tag toggles."""

import pytest

from database_crud import (
    add_item,
    add_list_tag,
    create_list,
    create_room,
    find_item_by_name,
    get_list_data,
    get_list_details,
    remove_list_tag,
    toggle_item_active_tag,
)
from database_setup import db


@pytest.fixture
def room_id():
    room_id_value, _ = create_room("Tag room", "pw")
    return room_id_value


def list_tags(list_id):
    return get_list_details(list_id)["list_tags"]


def item_tags(list_id, name):
    items = get_list_data(list_id)[0]
    return next(item["active_tags"] for item in items if item["name"] == name)


def test_new_list_has_no_tags(room_id):
    list_id, _ = create_list("groceries", room_id)
    assert list_tags(list_id) == []


def test_list_tags_are_sorted_case_insensitively(room_id):
    list_id, _ = create_list("groceries", room_id)
    for tag in ["dairy", "Bakery", "fruit"]:
        add_list_tag(list_id, tag)

    assert list_tags(list_id) == ["Bakery", "dairy", "fruit"]


def test_adding_an_existing_list_tag_changes_nothing(room_id):
    list_id, _ = create_list("groceries", room_id)
    add_list_tag(list_id, "dairy")
    add_list_tag(list_id, "dairy")

    assert list_tags(list_id) == ["dairy"]


def test_removing_a_missing_list_tag_changes_nothing(room_id):
    list_id, _ = create_list("groceries", room_id)
    add_list_tag(list_id, "dairy")
    remove_list_tag(list_id, "missing")

    assert list_tags(list_id) == ["dairy"]
    assert not db.in_transaction


def test_list_tags_belong_to_one_list(room_id):
    first_id, _ = create_list("first", room_id)
    second_id, _ = create_list("second", room_id)
    add_list_tag(first_id, "only-first")

    assert list_tags(first_id) == ["only-first"]
    assert list_tags(second_id) == []


def test_item_tag_toggle_adds_then_removes(room_id):
    list_id, _ = create_list("groceries", room_id)
    add_item("milk", list_id)
    item_id, _ = find_item_by_name(list_id, "milk")

    toggle_item_active_tag(item_id, list_id, "dairy")
    assert item_tags(list_id, "milk") == ["dairy"]

    toggle_item_active_tag(item_id, list_id, "dairy")
    assert item_tags(list_id, "milk") == []


def test_item_tag_toggle_ignores_an_item_from_another_list(room_id):
    own_list_id, _ = create_list("own", room_id)
    other_list_id, _ = create_list("other", room_id)
    add_item("milk", other_list_id)
    item_id, _ = find_item_by_name(other_list_id, "milk")

    toggle_item_active_tag(item_id, own_list_id, "dairy")

    assert item_tags(other_list_id, "milk") == []
    assert not db.in_transaction


def test_deleted_list_tag_keeps_item_tags_so_undo_restores_them(room_id):
    # Undo of a tag delete only re-adds the list tag. Items must keep their
    # tag, or undo would bring back an empty tag.
    list_id, _ = create_list("groceries", room_id)
    add_item("milk", list_id)
    item_id, _ = find_item_by_name(list_id, "milk")
    add_list_tag(list_id, "dairy")
    toggle_item_active_tag(item_id, list_id, "dairy")

    remove_list_tag(list_id, "dairy")
    assert list_tags(list_id) == []
    assert item_tags(list_id, "milk") == ["dairy"]

    add_list_tag(list_id, "dairy")
    assert item_tags(list_id, "milk") == ["dairy"]


@pytest.mark.parametrize("stored", ["not json", ""])
def test_unreadable_stored_list_tags_are_treated_as_empty(room_id, stored):
    list_id, _ = create_list("groceries", room_id)
    db.execute("UPDATE lists SET list_tags = ? WHERE id = ?", (stored, list_id))
    db.commit()

    assert list_tags(list_id) == []
    add_list_tag(list_id, "dairy")
    assert list_tags(list_id) == ["dairy"]


def test_unreadable_stored_item_tags_are_treated_as_empty(room_id):
    list_id, _ = create_list("groceries", room_id)
    add_item("milk", list_id)
    item_id, _ = find_item_by_name(list_id, "milk")
    db.execute("UPDATE items SET active_tags = 'not json' WHERE id = ?", (item_id,))
    db.commit()

    assert item_tags(list_id, "milk") == []
    toggle_item_active_tag(item_id, list_id, "dairy")
    assert item_tags(list_id, "milk") == ["dairy"]
