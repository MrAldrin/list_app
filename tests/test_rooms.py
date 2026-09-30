"""Regression tests for creating, listing, renaming and deleting rooms."""

import re

import pytest

import room_invitations as invitations
from database_crud import (
    add_item,
    authenticate_room_and_issue_token,
    create_list,
    create_room,
    delete_room,
    delete_room_with_password,
    get_list_data,
    get_lists,
    get_room_details_by_slug,
    get_rooms,
    rename_room,
    rename_room_with_room_token,
    verify_room,
)
from database_setup import db


def count(table):
    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def room_with_data(name):
    room_id, slug = create_room(name, "password")
    list_id, _ = create_list(f"{name} list", room_id)
    add_item("milk", list_id)
    return room_id, slug, list_id


def test_create_room_builds_a_readable_unique_slug():
    first_id, first_slug = create_room("Our Flat #2", "password")
    second_id, second_slug = create_room("Our Flat #2", "password")

    assert re.fullmatch(r"our-flat--2-[0-9a-f]{6}", first_slug)
    assert first_slug != second_slug
    assert first_id != second_id
    assert get_room_details_by_slug(first_slug) == {
        "id": first_id,
        "name": "Our Flat #2",
        "slug": first_slug,
    }


def test_room_names_trim_edges_and_keep_case_and_inner_spaces():
    _, admin_slug = create_room("  Our  Flat  ", "password")
    _, token = invitations.create_invitation()
    invited_slug = invitations.create_room_from_invitation(
        token, "  Øvre  Hytte  ", "password"
    )

    assert get_room_details_by_slug(admin_slug)["name"] == "Our  Flat"
    assert get_room_details_by_slug(invited_slug)["name"] == "Øvre  Hytte"


def test_room_renames_trim_edges_and_keep_case():
    room_id, slug = create_room("Before", "password")
    _, token = authenticate_room_and_issue_token(slug, "password")

    rename_room(room_id, "  Admin  Name  ")
    assert get_room_details_by_slug(slug)["name"] == "Admin  Name"

    rename_room_with_room_token(slug, token, "  Token  Name  ")
    assert get_room_details_by_slug(slug)["name"] == "Token  Name"


@pytest.mark.parametrize("rename", ["admin", "token"])
def test_room_renames_reject_blank_names(rename):
    room_id, slug = create_room("Keep", "password")
    _, token = authenticate_room_and_issue_token(slug, "password")

    with pytest.raises(ValueError, match="Room name cannot be empty"):
        if rename == "admin":
            rename_room(room_id, "   ")
        else:
            rename_room_with_room_token(slug, token, "   ")

    assert get_room_details_by_slug(slug)["name"] == "Keep"
    assert not db.in_transaction


def test_create_room_stores_only_a_password_hash():
    room_id, slug = create_room("Hashed", "secret-password")

    stored = db.execute(
        "SELECT password_hash FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]
    assert "secret-password" not in stored
    assert verify_room(slug, "secret-password") == room_id
    assert verify_room(slug, "wrong-password") is None


@pytest.mark.parametrize(
    ("name", "password", "message"),
    [
        ("", "password", "Room name cannot be empty"),
        ("   ", "password", "Room name cannot be empty"),
        ("Room", "", "Password cannot be empty"),
    ],
)
def test_create_room_rejects_empty_input_without_saving(name, password, message):
    before = count("rooms")

    with pytest.raises(ValueError, match=message):
        create_room(name, password)

    assert count("rooms") == before


def test_rooms_are_listed_by_name_ignoring_case():
    for name in ["bravo", "Alpha", "charlie"]:
        create_room(name, "password")

    names = [room["name"] for room in get_rooms()]
    assert names == sorted(names, key=str.lower)
    assert {"Alpha", "bravo", "charlie"} <= set(names)


def test_rename_room_keeps_slug_and_lists():
    room_id, slug, list_id = room_with_data("Before")

    rename_room(room_id, "After")

    assert get_room_details_by_slug(slug)["name"] == "After"
    assert [row[0] for row in get_lists(room_id)] == [list_id]


def test_delete_room_removes_only_its_own_data():
    room_id, slug, list_id = room_with_data("Doomed")
    kept_room_id, kept_slug, kept_list_id = room_with_data("Kept")

    delete_room(room_id)

    assert get_room_details_by_slug(slug) is None
    assert get_lists(room_id) == []
    assert get_list_data(list_id) == ([], [])
    assert get_room_details_by_slug(kept_slug)["id"] == kept_room_id
    assert [row[0] for row in get_lists(kept_room_id)] == [kept_list_id]
    assert len(get_list_data(kept_list_id)[0]) == 1


def test_delete_room_with_password_removes_room_lists_items_and_tokens():
    room_id, slug, list_id = room_with_data("Doomed")
    authenticate_room_and_issue_token(slug, "password")

    assert delete_room_with_password(slug, "password") is True

    assert get_room_details_by_slug(slug) is None
    assert get_lists(room_id) == []
    assert get_list_data(list_id) == ([], [])
    tokens = db.execute(
        "SELECT COUNT(*) FROM room_access_tokens WHERE room_id = ?", (room_id,)
    ).fetchone()[0]
    assert tokens == 0
    assert not db.in_transaction


def test_delete_room_with_wrong_password_keeps_everything():
    room_id, slug, list_id = room_with_data("Safe")

    assert delete_room_with_password(slug, "wrong-password") is False

    assert get_room_details_by_slug(slug)["id"] == room_id
    assert [row[0] for row in get_lists(room_id)] == [list_id]
    assert len(get_list_data(list_id)[0]) == 1
    assert not db.in_transaction


def test_delete_unknown_room_with_password_returns_false():
    before = count("rooms")

    assert delete_room_with_password("no-such-room", "password") is False

    assert count("rooms") == before
    assert not db.in_transaction
