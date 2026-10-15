"""Private list renames preserve uniqueness and report duplicate names."""

import pytest
from api_helpers import create_list, get_list_details, rename_list, write_locked

from database_crud import get_rooms, rename_list_if_unique_locked
from database_setup import db


@pytest.fixture
def rename_lists():
    room_id = get_rooms()[0]["id"]
    other_id, _ = create_list("other", room_id)
    list_id, slug = create_list("target", room_id)
    return room_id, list_id, slug, other_id


def test_normal_rename_preserves_list_identity_and_room(rename_lists):
    room_id, list_id, slug, _ = rename_lists

    assert write_locked(rename_list_if_unique_locked, list_id, room_id, "New List")

    details = get_list_details(list_id)
    assert details["name"] == "New List"
    assert details["slug"] == slug
    assert details["room_id"] == room_id
    assert not db.in_transaction


def test_existing_duplicate_returns_false_without_changing_lists(rename_lists):
    room_id, list_id, _, other_id = rename_lists
    before_target = get_list_details(list_id)
    before_other = get_list_details(other_id)

    assert (
        write_locked(rename_list_if_unique_locked, list_id, room_id, "other") is False
    )

    assert get_list_details(list_id) == before_target
    assert get_list_details(other_id) == before_other
    assert not db.in_transaction


def test_competing_rename_before_the_write_returns_false(rename_lists):
    room_id, list_id, _, other_id = rename_lists
    before_target = get_list_details(list_id)
    # The competing writer commits its name before this rename.
    rename_list(other_id, "claimed")

    assert (
        write_locked(rename_list_if_unique_locked, list_id, room_id, "claimed") is False
    )

    assert get_list_details(list_id) == before_target
    assert get_list_details(other_id)["name"] == "claimed"
    assert not db.in_transaction

    assert write_locked(rename_list_if_unique_locked, list_id, room_id, "valid")
    assert not db.in_transaction
