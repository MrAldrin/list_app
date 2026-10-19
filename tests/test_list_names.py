"""List names keep the user's case; items stay lowercase."""

import pytest
from api_helpers import (
    client_for,
    create_list,
    find_list_by_name,
    get_list_data,
    list_uid_of,
    lists_in_room,
    new_id,
    op,
    write_locked,
)

from database_crud import create_room, rename_list_if_unique_locked


@pytest.fixture
def room():
    room_id, slug = create_room("Names", "password")
    return room_id, slug


def list_names(room_id):
    return sorted(row[1] for row in lists_in_room(room_id))


def test_list_names_trim_edges_and_keep_case_and_inner_spaces(room):
    room_id, _ = room
    create_list("  Weekly  Shop  ", room_id)
    create_list("  Øl og  Brus ", room_id)

    assert list_names(room_id) == ["Weekly  Shop", "Øl og  Brus"]


@pytest.mark.parametrize("existing", ["Øl", "ØL", "øl"])
def test_list_duplicates_ignore_case_for_all_letters(room, existing):
    # SQLite NOCASE only folds A-Z, so Norwegian letters need the Python check.
    room_id, _ = room
    first_id, first_slug = create_list(existing, room_id)

    assert create_list(" øl ", room_id) == (first_id, first_slug)
    assert create_list("ØL", room_id) == (first_id, first_slug)
    assert find_list_by_name("øL", room_id) == (first_id,)
    assert list_names(room_id) == [existing]


def test_list_renames_keep_case_and_reject_unicode_duplicates(room):
    room_id, _ = room
    create_list("Øl", room_id)
    list_id, _ = create_list("Brus", room_id)

    # Names arrive trimmed, as the API sends them.
    assert write_locked(rename_list_if_unique_locked, list_id, room_id, "øl") is False
    assert write_locked(rename_list_if_unique_locked, list_id, room_id, "ØL") is False

    assert write_locked(rename_list_if_unique_locked, list_id, room_id, "Kaffe  og Te")
    assert write_locked(rename_list_if_unique_locked, list_id, room_id, "Kaffe")
    assert list_names(room_id) == ["Kaffe", "Øl"]


def test_renaming_a_list_to_a_new_case_of_its_own_name_is_allowed(room):
    room_id, _ = room
    list_id, _ = create_list("groceries", room_id)

    assert write_locked(rename_list_if_unique_locked, list_id, room_id, "Groceries")
    assert list_names(room_id) == ["Groceries"]


def test_item_names_are_still_lowercased(room):
    room_id, slug = room
    list_id, _ = create_list("Shop", room_id)
    client = client_for(slug, "password")

    response = op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.add",
            "list_uid": list_uid_of(list_id),
            "name": "  Oat MILK ",
        },
    )

    assert response["status"] == "applied"
    assert [item["name"] for item in get_list_data(list_id)[0]] == ["oat milk"]
