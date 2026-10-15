from api_helpers import (
    add_list_tag,
    create_list,
    get_list_data,
    get_list_details,
    get_list_details_by_share_token,
    insert_item,
    toggle_item_active_tag,
    validate_room_access_token,
    write_locked,
)

from database_crud import (
    adjust_item_quantity_locked,
    authenticate_room_and_issue_token,
    normalize_item_name,
    rename_list_if_unique_locked,
    update_item_details_locked,
)
from database_setup import db


def write_state(
    list_id: int,
) -> tuple[dict[str, object] | None, tuple[list[dict[str, object]], list[str]]]:
    return get_list_details(list_id), get_list_data(list_id)


def test_room_and_public_write_paths_preserve_list_and_item_state() -> None:
    room_id, room_slug = db.execute("SELECT id, slug FROM rooms").fetchone()
    authenticated_room_id, room_token = authenticate_room_and_issue_token(
        room_slug, "pw"
    )
    assert authenticated_room_id == room_id

    list_id, _ = create_list("groceries", room_id)
    share_token = get_list_details(list_id)["share_token"]
    occupied_list_id, _ = create_list("occupied", room_id)

    add_list_tag(list_id, "pantry")
    insert_item("milk", list_id)
    insert_item("bread", list_id)
    items, _ = get_list_data(list_id)
    milk_id = next(item["id"] for item in items if item["name"] == "milk")
    bread_id = next(item["id"] for item in items if item["name"] == "bread")
    assert (
        write_locked(
            update_item_details_locked, milk_id, list_id, "milk", "whole milk", 3
        )
        == "saved"
    )
    assert (
        write_locked(
            update_item_details_locked, bread_id, list_id, "bread", "sourdough", 2
        )
        == "saved"
    )
    toggle_item_active_tag(milk_id, list_id, "chilled")
    toggle_item_active_tag(bread_id, list_id, "bakery")

    # The next valid write keeps the old tags.
    add_list_tag(list_id, "seasonal")
    assert not db.in_transaction

    # A valid room grant still cannot rename a list to a duplicate name.
    before = write_state(list_id)
    assert (
        write_locked(rename_list_if_unique_locked, list_id, room_id, "occupied")
        is False
    )
    assert write_state(list_id) == before
    assert not db.in_transaction

    # The valid room-path rename succeeds without rotating either list identity.
    assert (
        write_locked(rename_list_if_unique_locked, list_id, room_id, "weekly groceries")
        is True
    )
    assert not db.in_transaction
    details = get_list_details(list_id)
    assert details["name"] == "weekly groceries"
    assert details["share_token"] == share_token
    assert details["list_tags"] == ["pantry", "seasonal"]
    assert validate_room_access_token(room_slug, room_token) == room_id
    assert get_list_details_by_share_token(share_token)["id"] == list_id
    assert get_list_details(occupied_list_id)["name"] == "occupied"

    # A cross-item duplicate is rejected without changing any field or tag.
    before = write_state(list_id)
    assert (
        write_locked(
            update_item_details_locked,
            milk_id,
            list_id,
            normalize_item_name(" BREAD "),
            "must not save",
            9,
        )
        == "duplicate"
    )
    assert write_state(list_id) == before
    assert not db.in_transaction

    # A valid edit and quantity delta still work.
    assert (
        write_locked(
            update_item_details_locked, milk_id, list_id, "oat milk", "unsweetened", 4
        )
        == "saved"
    )
    assert not db.in_transaction
    assert write_locked(adjust_item_quantity_locked, milk_id, list_id, 2) is True
    toggle_item_active_tag(milk_id, list_id, "organic")
    add_list_tag(list_id, "favorites")

    details = get_list_details(list_id)
    assert details["share_token"] == share_token
    assert details["list_tags"] == ["favorites", "pantry", "seasonal"]
    assert validate_room_access_token(room_slug, room_token) == room_id
    assert get_list_details_by_share_token(share_token)["id"] == list_id

    items, _ = get_list_data(list_id)
    stored = {item["id"]: item for item in items}
    assert (
        stored[milk_id]["name"],
        stored[milk_id]["description"],
        stored[milk_id]["quantity"],
        set(stored[milk_id]["active_tags"]),
    ) == ("oat milk", "unsweetened", 6, {"chilled", "organic"})
    assert (
        stored[bread_id]["name"],
        stored[bread_id]["description"],
        stored[bread_id]["quantity"],
        stored[bread_id]["active_tags"],
    ) == ("bread", "sourdough", 2, ["bakery"])
    assert not db.in_transaction
