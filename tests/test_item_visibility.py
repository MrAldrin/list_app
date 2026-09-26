import sqlite3
from datetime import UTC, datetime

import pytest

import database_crud as crud
from database_setup import db
from item_service import add_or_restore_item
from item_visibility import (
    DEFAULT_HIDE_DONE_AGE_DAYS,
    DEFAULT_HIDE_DONE_MODE,
    DEFAULT_HIDE_DONE_RECENT_COUNT,
    MAX_HIDE_DONE_COUNT,
    filter_visible_items,
)


def _item(item_id, done, completed_at=None):
    return {"id": item_id, "done": done, "completed_at": completed_at}


def _stored_item(list_id, item_id):
    items, _ = crud.get_list_data(list_id)
    return next(item for item in items if item["id"] == item_id)


def test_visibility_modes_keep_unchecked_and_legacy_checked_items_as_specified():
    items = [
        _item(1, False),
        _item(2, True),
        _item(3, True, "2025-01-07T12:00:00Z"),
    ]
    now = datetime(2025, 1, 8, 12, tzinfo=UTC)

    assert [row["id"] for row in filter_visible_items(items)] == [1, 2, 3]
    assert [row["id"] for row in filter_visible_items(items, "all")] == [1]
    assert [row["id"] for row in filter_visible_items(items, "age", 1, now=now)] == [
        1,
        2,
    ]
    assert [row["id"] for row in filter_visible_items(items, "age", 0, now=now)] == [
        1,
    ]
    assert items[1]["completed_at"] is None


def test_age_zero_hides_checked_items_even_with_future_timestamps():
    now = datetime(2025, 1, 8, 12, tzinfo=UTC)
    items = [_item(1, False), _item(2, True, "2030-01-01T00:00:00Z")]

    assert [row["id"] for row in filter_visible_items(items, "age", 0, now=now)] == [1]


def test_age_visibility_uses_exact_full_24_hour_boundary():
    now = datetime(2025, 1, 8, 12, tzinfo=UTC)
    items = [
        _item(1, True, "2025-01-01T12:00:00Z"),
        _item(2, True, "2025-01-01T12:00:01Z"),
        _item(3, True, "2025-01-01T11:59:59Z"),
        _item(4, False),
    ]

    visible = filter_visible_items(items, "age", age_days=7, now=now)

    assert [row["id"] for row in visible] == [2, 4]


def test_recent_visibility_ranks_known_times_then_timestamp_ties_and_legacy_ids():
    items = [
        _item(99, True),
        _item(4, True, "2025-01-03T00:00:00Z"),
        _item(7, True, "2025-01-02T00:00:00Z"),
        _item(8, True, "2025-01-02T00:00:00Z"),
        _item(10, True, "2025-01-01T00:00:00Z"),
        _item(19, True),
        _item(20, True),
        _item(21, False),
    ]

    retained = filter_visible_items(items, "recent", recent_count=2)
    retained_legacy = filter_visible_items(items, "recent", recent_count=5)
    retained_all = filter_visible_items(items, "recent", recent_count=7)
    none_retained = filter_visible_items(items, "recent", recent_count=0)

    assert {row["id"] for row in retained} == {4, 8, 21}
    assert {row["id"] for row in retained_legacy} == {4, 7, 8, 10, 21, 99}
    assert {row["id"] for row in retained_all} == {4, 7, 8, 10, 19, 20, 21, 99}
    assert [row["id"] for row in none_retained] == [21]


def test_visibility_helper_validates_mode_and_count_bounds():
    with pytest.raises(ValueError, match="Unknown checked-item visibility mode"):
        filter_visible_items([], "unknown")
    with pytest.raises(ValueError, match="age_days"):
        filter_visible_items([], "age", age_days=-1)
    with pytest.raises(ValueError, match="recent_count"):
        filter_visible_items([], "recent", recent_count=True)
    with pytest.raises(ValueError, match="recent_count"):
        filter_visible_items([], "recent", recent_count=MAX_HIDE_DONE_COUNT + 1)


def test_visibility_setting_defaults_and_atomic_identity_checked_update():
    room_id = crud.get_rooms()[0]["id"]
    list_id, slug = crud.create_list("visibility", room_id)

    defaults = crud.get_list_details(list_id)
    assert defaults["hide_done_mode"] == DEFAULT_HIDE_DONE_MODE
    assert defaults["hide_done_age_days"] == DEFAULT_HIDE_DONE_AGE_DAYS
    assert defaults["hide_done_recent_count"] == DEFAULT_HIDE_DONE_RECENT_COUNT
    assert crud.get_list_details_by_slug(slug)["hide_done_mode"] == "off"

    crud.update_list_visibility_settings(
        list_id, mode="recent", age_days=0, recent_count=4, expected_slug=slug
    )

    updated = crud.get_list_details(list_id)
    assert (
        updated["hide_done_mode"],
        updated["hide_done_age_days"],
        updated["hide_done_recent_count"],
    ) == ("recent", 0, 4)
    assert crud.get_list_details_by_slug(slug)["hide_done_recent_count"] == 4


@pytest.mark.parametrize(
    ("mode", "age_days", "recent_count"),
    [
        ("unknown", 7, 10),
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
    list_id, slug = crud.create_list("visibility", room_id)
    before = crud.get_list_details(list_id)

    with pytest.raises(ValueError):
        crud.update_list_visibility_settings(
            list_id,
            mode=mode,
            age_days=age_days,
            recent_count=recent_count,
            expected_slug=slug,
        )

    assert crud.get_list_details(list_id) == before
    assert not db.in_transaction


def test_failed_visibility_settings_write_rolls_back_and_recovers():
    room_id = crud.get_rooms()[0]["id"]
    list_id, slug = crud.create_list("visibility", room_id)
    before = crud.get_list_details(list_id)
    db.execute(
        "CREATE TEMP TRIGGER fail_visibility_settings "
        "BEFORE UPDATE OF hide_done_mode ON lists "
        f"WHEN OLD.id = {list_id} "
        "BEGIN SELECT RAISE(ABORT, 'injected visibility failure'); END"
    )
    try:
        with pytest.raises(sqlite3.IntegrityError, match="injected visibility"):
            crud.update_list_visibility_settings(
                list_id,
                mode="all",
                age_days=3,
                recent_count=5,
                expected_slug=slug,
            )

        assert crud.get_list_details(list_id) == before
        assert not db.in_transaction

        db.execute("DROP TRIGGER fail_visibility_settings")
        crud.update_list_visibility_settings(
            list_id,
            mode="age",
            age_days=3,
            recent_count=5,
            expected_slug=slug,
        )
        assert crud.get_list_details(list_id)["hide_done_mode"] == "age"
        assert not db.in_transaction
    finally:
        db.rollback()
        db.execute("DROP TRIGGER IF EXISTS fail_visibility_settings")
        db.commit()


def test_completion_timestamp_tracks_transitions_and_add_search_restoration():
    room_id = crud.get_rooms()[0]["id"]
    list_id, slug = crud.create_list("completion", room_id)
    crud.add_item("Milk", list_id, expected_slug=slug)
    item_id = crud.find_item_by_name(list_id, "milk")[0]
    completed_first = datetime(2025, 1, 1, 12, tzinfo=UTC)
    completed_again = datetime(2025, 1, 2, 12, tzinfo=UTC)

    crud.update_item_done(item_id, list_id, True, now=completed_first)
    first_timestamp = _stored_item(list_id, item_id)["completed_at"]
    crud.update_item_done(item_id, list_id, True, now=completed_again)
    assert _stored_item(list_id, item_id)["completed_at"] == first_timestamp

    crud.update_item_done(item_id, list_id, False, now=completed_again)
    assert _stored_item(list_id, item_id)["completed_at"] is None
    crud.update_item_done(item_id, list_id, True, now=completed_again)
    assert (
        _stored_item(list_id, item_id)["completed_at"] == "2025-01-02T12:00:00.000000Z"
    )

    crud.restore_item(item_id, list_id, expected_slug=slug)
    assert _stored_item(list_id, item_id)["completed_at"] is None
    crud.update_item_done(item_id, list_id, True, now=completed_first)
    assert filter_visible_items(crud.get_list_data(list_id)[0], "all") == []
    assert add_or_restore_item(list_id, "milk", expected_slug=slug) == (
        "restored",
        "milk",
    )
    assert _stored_item(list_id, item_id)["completed_at"] is None

    items, history = crud.get_list_data(list_id)
    assert len(items) == 1
    assert history == ["Milk"]


def test_checked_item_insert_gets_utc_timestamp_and_get_list_data_keeps_history():
    room_id = crud.get_rooms()[0]["id"]
    list_id, slug = crud.create_list("completion", room_id)
    instant = datetime(2025, 1, 1, 15, tzinfo=UTC)

    crud.add_item_with_state(
        "already done", list_id, True, [], expected_slug=slug, now=instant
    )

    items, history = crud.get_list_data(list_id)
    assert items[0]["completed_at"] == "2025-01-01T15:00:00.000000Z"
    assert items[0]["done"] is True
    assert history == ["already done"]
    assert filter_visible_items(items, "all") == []
