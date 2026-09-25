import pytest

from database_crud import (
    RoomAccessDenied,
    add_item,
    add_list_tag,
    authenticate_room_and_issue_token,
    create_list_with_room_token,
    get_list_data,
    get_list_details,
    get_list_details_by_share_token,
    rename_list_with_room_token,
    toggle_item_active_tag,
    validate_room_access_token,
)
from database_setup import db
from item_service import (
    STATUS_DUPLICATE_NAME,
    STATUS_RENAMED,
    STATUS_UPDATED,
    change_item_quantity,
    update_item_details_with_checks,
)


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

    list_id, list_slug = create_list_with_room_token(room_slug, room_token, "groceries")
    share_token = get_list_details(list_id)["share_token"]
    share_identity = f"share:{share_token}"
    occupied_list_id, _ = create_list_with_room_token(room_slug, room_token, "occupied")

    add_list_tag(list_id, "pantry", expected_slug=list_slug)
    add_item("milk", list_id, expected_slug=share_identity)
    add_item("bread", list_id, expected_slug=share_identity)
    items, _ = get_list_data(list_id)
    milk_id = next(item["id"] for item in items if item["name"] == "milk")
    bread_id = next(item["id"] for item in items if item["name"] == "bread")
    assert update_item_details_with_checks(
        list_id, milk_id, "milk", "whole milk", 3, expected_slug=share_identity
    ) == (STATUS_RENAMED, "milk")
    assert update_item_details_with_checks(
        list_id, bread_id, "bread", "sourdough", 2, expected_slug=share_identity
    ) == (STATUS_RENAMED, "bread")
    toggle_item_active_tag(milk_id, list_id, "chilled", expected_slug=share_identity)
    toggle_item_active_tag(bread_id, list_id, "bakery", expected_slug=share_identity)

    # A public list token can edit list contents, but cannot authorize room management.
    before = write_state(list_id)
    with pytest.raises(RoomAccessDenied):
        rename_list_with_room_token(
            room_slug, share_token, list_id, "forbidden", expected_slug=list_slug
        )
    assert write_state(list_id) == before
    assert not db.in_transaction

    # The next valid write uses the private list identity and preserves old tags.
    add_list_tag(list_id, "seasonal", expected_slug=list_slug)
    assert not db.in_transaction

    # A valid room grant still cannot rename a list to a duplicate name.
    before = write_state(list_id)
    with pytest.raises(ValueError, match="already exists"):
        rename_list_with_room_token(
            room_slug, room_token, list_id, "occupied", expected_slug=list_slug
        )
    assert write_state(list_id) == before
    assert not db.in_transaction

    # The valid room-path rename succeeds without rotating either list identity.
    assert (
        rename_list_with_room_token(
            room_slug, room_token, list_id, "weekly groceries", expected_slug=list_slug
        )
        == "weekly groceries"
    )
    assert not db.in_transaction
    details = get_list_details(list_id)
    assert details["name"] == "weekly groceries"
    assert details["slug"] == list_slug
    assert details["share_token"] == share_token
    assert details["list_tags"] == ["pantry", "seasonal"]
    assert validate_room_access_token(room_slug, room_token) == room_id
    assert get_list_details_by_share_token(share_token)["id"] == list_id
    assert get_list_details(occupied_list_id)["name"] == "occupied"

    # A cross-item duplicate is rejected without changing any field or tag.
    before = write_state(list_id)
    status, normalized_name = update_item_details_with_checks(
        list_id, milk_id, " BREAD ", "must not save", 9, expected_slug=share_identity
    )
    assert (status, normalized_name) == (STATUS_DUPLICATE_NAME, "bread")
    assert write_state(list_id) == before
    assert not db.in_transaction

    # A valid edit and quantity delta still work through the public list identity.
    assert update_item_details_with_checks(
        list_id,
        milk_id,
        "oat milk",
        "unsweetened",
        4,
        expected_slug=share_identity,
    ) == (STATUS_RENAMED, "oat milk")
    assert not db.in_transaction
    assert (
        change_item_quantity(list_id, milk_id, 2, expected_slug=share_identity)
        == STATUS_UPDATED
    )
    toggle_item_active_tag(milk_id, list_id, "organic", expected_slug=share_identity)
    add_list_tag(list_id, "favorites", expected_slug=list_slug)

    details = get_list_details(list_id)
    assert details["slug"] == list_slug
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
