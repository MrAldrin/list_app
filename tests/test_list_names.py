"""List names keep the user's case; items stay lowercase."""

import pytest

from database_crud import (
    authenticate_room_and_issue_token,
    create_list,
    create_list_with_room_token,
    create_room,
    find_list_by_name,
    get_list_data,
    get_lists,
    rename_list_with_room_token,
)
from item_service import (
    STATUS_DUPLICATE_NAME,
    STATUS_RENAMED,
    add_or_restore_item,
    rename_list_with_checks,
)


@pytest.fixture
def room():
    room_id, slug = create_room("Names", "password")
    _, token = authenticate_room_and_issue_token(slug, "password")
    return room_id, slug, token


def list_names(room_id):
    return [row[1] for row in get_lists(room_id)]


def test_list_names_trim_edges_and_keep_case_and_inner_spaces(room):
    room_id, slug, token = room
    create_list("  Weekly  Shop  ", room_id)
    create_list_with_room_token(slug, token, "  Øl og  Brus ")

    assert list_names(room_id) == ["Weekly  Shop", "Øl og  Brus"]


@pytest.mark.parametrize("existing", ["Øl", "ØL", "øl"])
def test_list_duplicates_ignore_case_for_all_letters(room, existing):
    # SQLite NOCASE only folds A-Z, so Norwegian letters need the Python check.
    room_id, slug, token = room
    first_id, first_slug = create_list(existing, room_id)

    assert create_list(" øl ", room_id) == (first_id, first_slug)
    assert create_list_with_room_token(slug, token, "ØL") == (first_id, first_slug)
    assert find_list_by_name("øL", room_id) == (first_id,)
    assert list_names(room_id) == [existing]


def test_list_renames_keep_case_and_reject_unicode_duplicates(room):
    room_id, slug, token = room
    create_list("Øl", room_id)
    list_id, list_slug = create_list("Brus", room_id)

    status, name = rename_list_with_checks(
        list_id, room_id, "  øl  ", expected_slug=list_slug
    )
    assert (status, name) == (STATUS_DUPLICATE_NAME, "øl")
    with pytest.raises(ValueError, match="already exists"):
        rename_list_with_room_token(slug, token, list_id, "ØL", expected_slug=list_slug)

    status, name = rename_list_with_checks(
        list_id, room_id, "  Kaffe  og Te ", expected_slug=list_slug
    )
    assert (status, name) == (STATUS_RENAMED, "Kaffe  og Te")
    assert (
        rename_list_with_room_token(
            slug, token, list_id, " Kaffe ", expected_slug=list_slug
        )
        == "Kaffe"
    )
    assert list_names(room_id) == ["Kaffe", "Øl"]


def test_renaming_a_list_to_a_new_case_of_its_own_name_is_allowed(room):
    room_id, _, _ = room
    list_id, list_slug = create_list("groceries", room_id)

    status, name = rename_list_with_checks(
        list_id, room_id, "Groceries", expected_slug=list_slug
    )

    assert (status, name) == (STATUS_RENAMED, "Groceries")
    assert list_names(room_id) == ["Groceries"]


def test_item_names_are_still_lowercased(room):
    room_id, _, _ = room
    list_id, _ = create_list("Shop", room_id)
    add_or_restore_item(list_id, "  Oat MILK ")

    assert [item["name"] for item in get_list_data(list_id)[0]] == ["oat milk"]


def test_buttons_show_names_as_typed():
    # Quasar buttons draw text in capitals unless no-caps is set.
    from nicegui import Client, ui
    from nicegui.page import page

    import main

    with Client(page("/")):
        button = main.ui.button("Weekly Shop")

    assert isinstance(button, ui.button)
    assert button.text == "Weekly Shop"
    assert button._props.get("no-caps") is True
