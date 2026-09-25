"""Undo restores the deleted snapshot without overwriting a newer item."""

import database_crud as crud
from main import _restore_pending_undo


def pending(name, done=False, tags=None, description="", quantity=1):
    return {
        "kind": "item",
        "payload": {
            "name": name,
            "done": done,
            "active_tags": tags if tags is not None else [],
            "description": description,
            "quantity": quantity,
        },
        "token": "test",
        "message": "Deleted item",
    }


def test_undo_restores_all_fields_after_delete(monkeypatch):
    notifications = []
    monkeypatch.setattr(
        "main.ui.notify", lambda *args, **kwargs: notifications.append(args)
    )
    room_id = crud.get_rooms()[0]["id"]
    list_id, slug = crud.create_list("shopping", room_id)
    original = pending("Milk", True, ["cold", "weekly"], "whole milk", 4)
    assert crud.restore_deleted_item(list_id, **original["payload"], expected_slug=slug)
    old_id = crud.find_item_by_name(list_id, "Milk")[0]
    crud.delete_item(old_id, list_id, expected_slug=slug)

    _restore_pending_undo(list_id, original, list_slug=slug)
    items, _ = crud.get_list_data(list_id)
    assert [{k: v for k, v in item.items() if k != "id"} for item in items] == [
        original["payload"]
    ]
    assert notifications[-1] == ("Restored Milk",)


def test_undo_conflict_does_not_change_new_item(monkeypatch):
    notifications = []
    monkeypatch.setattr(
        "main.ui.notify", lambda *args, **kwargs: notifications.append(args)
    )
    room_id = crud.get_rooms()[0]["id"]
    list_id, slug = crud.create_list("shopping", room_id)
    crud.add_item(" milk ", list_id)
    before = crud.get_list_data(list_id)

    _restore_pending_undo(
        list_id, pending("Milk", True, ["old"], "old notes", 7), list_slug=slug
    )
    assert crud.get_list_data(list_id) == before
    assert notifications[-1] == ("Cannot undo: item name already exists",)


def test_undo_keeps_existing_item_id_policy(monkeypatch):
    monkeypatch.setattr("main.ui.notify", lambda *args, **kwargs: None)
    room_id = crud.get_rooms()[0]["id"]
    list_id, slug = crud.create_list("shopping", room_id)
    crud.add_item("first", list_id)
    old_id = crud.find_item_by_name(list_id, "first")[0]
    crud.delete_item(old_id, list_id)
    crud.add_item("second", list_id)
    _restore_pending_undo(list_id, pending("first"), list_slug=slug)
    assert crud.find_item_by_name(list_id, "first")[0] != old_id
