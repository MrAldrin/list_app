"""Private list renames preserve uniqueness and report duplicate names."""

import pytest

import item_service
from database_crud import (
    ListUnavailable,
    create_list,
    create_room,
    delete_list,
    get_list_details,
    get_rooms,
    rename_list,
)
from database_setup import db
from item_service import (
    STATUS_DUPLICATE_NAME,
    STATUS_RENAMED,
    rename_list_with_checks,
)


@pytest.fixture
def rename_lists():
    room_id = get_rooms()[0]["id"]
    other_id, other_slug = create_list("other", room_id)
    list_id, slug = create_list("target", room_id)
    return room_id, list_id, slug, other_id, other_slug


def test_normal_rename_preserves_list_identity_and_room(rename_lists):
    room_id, list_id, slug, _, _ = rename_lists

    status, name = rename_list_with_checks(
        list_id, room_id, "  New List  ", expected_slug=slug
    )

    assert (status, name) == (STATUS_RENAMED, "new list")
    details = get_list_details(list_id)
    assert details["name"] == "new list"
    assert details["slug"] == slug
    assert details["room_id"] == room_id
    assert not db.in_transaction


def test_existing_duplicate_returns_status_without_changing_lists(rename_lists):
    room_id, list_id, slug, other_id, _ = rename_lists
    before_target = get_list_details(list_id)
    before_other = get_list_details(other_id)

    status, name = rename_list_with_checks(
        list_id, room_id, " OTHER ", expected_slug=slug
    )

    assert (status, name) == (STATUS_DUPLICATE_NAME, "other")
    assert get_list_details(list_id) == before_target
    assert get_list_details(other_id) == before_other
    assert not db.in_transaction


def test_competing_rename_before_atomic_check_returns_duplicate_status(
    rename_lists, monkeypatch
):
    room_id, list_id, slug, other_id, other_slug = rename_lists
    before_target = get_list_details(list_id)
    rename_if_unique = item_service.rename_list_if_unique
    competitor_renamed = False

    def compete_then_rename(**kwargs):
        nonlocal competitor_renamed
        if kwargs["new_name"] == "claimed" and not competitor_renamed:
            rename_list(other_id, "claimed", expected_slug=other_slug)
            competitor_renamed = True
        return rename_if_unique(**kwargs)

    monkeypatch.setattr(item_service, "rename_list_if_unique", compete_then_rename)
    status, name = rename_list_with_checks(
        list_id, room_id, "claimed", expected_slug=slug
    )

    assert competitor_renamed
    assert (status, name) == (STATUS_DUPLICATE_NAME, "claimed")
    assert get_list_details(list_id) == before_target
    assert get_list_details(other_id)["name"] == "claimed"
    assert not db.in_transaction

    next_status, next_name = rename_list_with_checks(
        list_id, room_id, "valid", expected_slug=slug
    )
    assert (next_status, next_name) == (STATUS_RENAMED, "valid")
    assert not db.in_transaction


def test_stale_list_identity_is_rejected_before_duplicate_lookup(rename_lists):
    room_id, old_list_id, old_slug, competing_id, competing_slug = rename_lists
    rename_list(competing_id, "claimed", expected_slug=competing_slug)
    delete_list(old_list_id, expected_slug=old_slug)
    replacement_id, replacement_slug = create_list("replacement", room_id)
    assert replacement_id == old_list_id
    before_replacement = get_list_details(replacement_id)
    before_competitor = get_list_details(competing_id)

    with pytest.raises(ListUnavailable):
        rename_list_with_checks(
            replacement_id, room_id, "claimed", expected_slug=old_slug
        )

    assert get_list_details(replacement_id) == before_replacement
    assert get_list_details(competing_id) == before_competitor
    assert not db.in_transaction

    status, name = rename_list_with_checks(
        replacement_id, room_id, "current", expected_slug=replacement_slug
    )
    assert (status, name) == (STATUS_RENAMED, "current")
    assert not db.in_transaction


def test_private_rename_does_not_mutate_a_list_from_another_room(rename_lists):
    room_id, list_id, slug, _, _ = rename_lists
    other_room_id, _ = create_room("Other room", "other-password")
    before = get_list_details(list_id)

    with pytest.raises(ListUnavailable):
        rename_list_with_checks(list_id, other_room_id, "forbidden", expected_slug=slug)

    assert get_list_details(list_id) == before
    assert before["room_id"] == room_id
    assert not db.in_transaction
