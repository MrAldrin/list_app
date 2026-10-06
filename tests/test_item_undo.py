"""Undo of a delete: restoring an item or a tag never overwrites newer data.

The undo bar lives in the Svelte app now (the `item.restore` op,
tests/test_api_item_ops.py). These tests keep the database rules underneath.
"""

import database_crud as crud
from database_setup import db


def snapshot_fields():
    return {
        "name": "Milk",
        "done": True,
        "active_tags": ["cold", "weekly"],
        "description": "whole milk",
        "quantity": 4,
        "completed_at": "2025-01-02T03:04:05.000000Z",
    }


def new_list(name="shopping"):
    room_id = crud.get_rooms()[0]["id"]
    return crud.create_list(name, room_id)


def test_restore_brings_back_all_fields_after_delete():
    list_id, slug = new_list()
    original = snapshot_fields()
    assert crud.restore_deleted_item(list_id, **original, expected_slug=slug)
    old_id = crud.find_item_by_name(list_id, "Milk")[0]
    crud.delete_item(old_id, list_id, expected_slug=slug)

    assert crud.restore_deleted_item(list_id, **original, expected_slug=slug)
    items, _ = crud.get_list_data(list_id)
    assert [{k: v for k, v in item.items() if k != "id"} for item in items] == [
        original
    ]


def test_restore_conflict_does_not_change_the_new_item():
    list_id, slug = new_list()
    crud.add_item(" milk ", list_id)
    before = crud.get_list_data(list_id)

    restored = crud.restore_deleted_item(
        list_id,
        name="Milk",
        done=True,
        active_tags=["old"],
        description="old notes",
        quantity=7,
        expected_slug=slug,
    )

    assert not restored
    assert crud.get_list_data(list_id) == before


def test_restore_gets_a_new_item_id():
    list_id, slug = new_list()
    crud.add_item("first", list_id)
    old_id = crud.find_item_by_name(list_id, "first")[0]
    crud.delete_item(old_id, list_id)
    crud.add_item("second", list_id)

    assert crud.restore_deleted_item(
        list_id,
        name="first",
        done=False,
        active_tags=[],
        description="",
        quantity=1,
        expected_slug=slug,
    )
    assert crud.find_item_by_name(list_id, "first")[0] != old_id


def test_restoring_a_tag_keeps_a_tag_added_in_between():
    list_id, slug = new_list()
    crud.add_list_tag(list_id, "concurrent-add", expected_slug=slug)

    crud.add_list_tag(list_id, "restored-tag", expected_slug=slug)

    details = crud.get_list_details(list_id)
    assert details["list_tags"] == ["concurrent-add", "restored-tag"]
    assert not db.in_transaction
