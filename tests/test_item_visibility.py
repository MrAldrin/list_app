import sqlite3
from datetime import UTC, datetime

import pytest
from api_helpers import (
    add_item_with_state,
    create_list,
    find_item_by_name,
    get_list_data,
    get_list_details,
    get_list_details_by_slug,
    insert_item,
    restore_item,
    update_list_visibility_settings,
    write_locked,
)

import database_crud as crud
from database_setup import db
from item_visibility import (
    DEFAULT_HIDE_DONE_AGE_DAYS,
    DEFAULT_HIDE_DONE_MODE,
    DEFAULT_HIDE_DONE_RECENT_COUNT,
    MAX_HIDE_DONE_COUNT,
    validate_visibility_settings,
)


def _stored_item(list_id, item_id):
    items, _ = get_list_data(list_id)
    return next(item for item in items if item["id"] == item_id)


@pytest.mark.parametrize("mode, age, recent", [("age", 0, 10), ("recent", 7, 0)])
def test_zero_counts_are_rejected(mode: str, age: int, recent: int) -> None:
    with pytest.raises(ValueError, match="between 1"):
        validate_visibility_settings(mode, age, recent)


def test_visibility_settings_validate_mode_and_count_bounds():
    with pytest.raises(ValueError, match="Unknown checked-item visibility mode"):
        validate_visibility_settings("unknown", 7, 10)
    with pytest.raises(ValueError, match="age_days"):
        validate_visibility_settings("age", -1, 10)
    with pytest.raises(ValueError, match="recent_count"):
        validate_visibility_settings("recent", 7, True)
    with pytest.raises(ValueError, match="recent_count"):
        validate_visibility_settings("recent", 7, MAX_HIDE_DONE_COUNT + 1)


def test_visibility_setting_defaults_and_atomic_identity_checked_update():
    room_id = crud.get_rooms()[0]["id"]
    list_id, slug = create_list("visibility", room_id)

    defaults = get_list_details(list_id)
    assert defaults["hide_done_mode"] == DEFAULT_HIDE_DONE_MODE
    assert defaults["hide_done_age_days"] == DEFAULT_HIDE_DONE_AGE_DAYS
    assert defaults["hide_done_recent_count"] == DEFAULT_HIDE_DONE_RECENT_COUNT
    assert get_list_details_by_slug(slug)["hide_done_mode"] == "off"

    update_list_visibility_settings(list_id, mode="recent", age_days=1, recent_count=4)

    updated = get_list_details(list_id)
    assert (
        updated["hide_done_mode"],
        updated["hide_done_age_days"],
        updated["hide_done_recent_count"],
    ) == ("recent", 1, 4)
    assert get_list_details_by_slug(slug)["hide_done_recent_count"] == 4


@pytest.mark.parametrize(
    ("mode", "age_days", "recent_count"),
    [
        ("unknown", 7, 10),
        ("off", 0, 10),
        ("off", 7, 0),
        ("off", -1, 10),
        ("off", 7, -1),
        ("off", True, 10),
        ("off", 7, 1.5),
        ("age", MAX_HIDE_DONE_COUNT + 1, 10),
        ("recent", 7, MAX_HIDE_DONE_COUNT + 1),
    ],
)
def test_visibility_settings_reject_invalid_values_without_writing(
    mode, age_days, recent_count
):
    room_id = crud.get_rooms()[0]["id"]
    list_id, _ = create_list("visibility", room_id)
    before = get_list_details(list_id)

    with pytest.raises(ValueError):
        update_list_visibility_settings(
            list_id,
            mode=mode,
            age_days=age_days,
            recent_count=recent_count,
        )

    assert get_list_details(list_id) == before
    assert not db.in_transaction


def test_failed_visibility_settings_write_rolls_back_and_recovers():
    room_id = crud.get_rooms()[0]["id"]
    list_id, _ = create_list("visibility", room_id)
    before = get_list_details(list_id)
    db.execute(
        "CREATE TEMP TRIGGER fail_visibility_settings "
        "BEFORE UPDATE OF hide_done_mode ON lists "
        f"WHEN OLD.id = {list_id} "
        "BEGIN SELECT RAISE(ABORT, 'injected visibility failure'); END"
    )
    try:
        with pytest.raises(sqlite3.IntegrityError, match="injected visibility"):
            update_list_visibility_settings(
                list_id,
                mode="all",
                age_days=3,
                recent_count=5,
            )

        assert get_list_details(list_id) == before
        assert not db.in_transaction

        db.execute("DROP TRIGGER fail_visibility_settings")
        update_list_visibility_settings(
            list_id,
            mode="age",
            age_days=3,
            recent_count=5,
        )
        assert get_list_details(list_id)["hide_done_mode"] == "age"
        assert not db.in_transaction
    finally:
        db.rollback()
        db.execute("DROP TRIGGER IF EXISTS fail_visibility_settings")
        db.commit()


def test_completion_timestamp_tracks_transitions_and_add_search_restoration():
    room_id = crud.get_rooms()[0]["id"]
    list_id, _ = create_list("completion", room_id)
    insert_item("Milk", list_id)
    item_id = find_item_by_name(list_id, "milk")[0]
    completed_first = datetime(2025, 1, 1, 12, tzinfo=UTC)
    completed_again = datetime(2025, 1, 2, 12, tzinfo=UTC)

    write_locked(
        crud.update_item_done_locked, item_id, list_id, True, now=completed_first
    )
    first_timestamp = _stored_item(list_id, item_id)["completed_at"]
    write_locked(
        crud.update_item_done_locked, item_id, list_id, True, now=completed_again
    )
    assert _stored_item(list_id, item_id)["completed_at"] == first_timestamp

    write_locked(
        crud.update_item_done_locked, item_id, list_id, False, now=completed_again
    )
    assert _stored_item(list_id, item_id)["completed_at"] is None
    write_locked(
        crud.update_item_done_locked, item_id, list_id, True, now=completed_again
    )
    assert (
        _stored_item(list_id, item_id)["completed_at"] == "2025-01-02T12:00:00.000000Z"
    )

    restore_item(item_id, list_id)
    assert _stored_item(list_id, item_id)["completed_at"] is None
    write_locked(
        crud.update_item_done_locked, item_id, list_id, True, now=completed_first
    )
    assert (
        write_locked(crud.add_or_restore_item_locked, "milk", list_id)[0] == "restored"
    )
    assert _stored_item(list_id, item_id)["completed_at"] is None

    items, history = get_list_data(list_id)
    assert len(items) == 1
    assert history == ["milk"]


def test_checked_item_insert_gets_utc_timestamp_and_get_list_data_keeps_history():
    room_id = crud.get_rooms()[0]["id"]
    list_id, _ = create_list("completion", room_id)
    instant = datetime(2025, 1, 1, 15, tzinfo=UTC)

    add_item_with_state("already done", list_id, True, [], now=instant)

    items, history = get_list_data(list_id)
    assert items[0]["completed_at"] == "2025-01-01T15:00:00.000000Z"
    assert items[0]["done"] is True
    assert history == ["already done"]
