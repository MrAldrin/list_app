"""The durable start of each dated due cycle (`items.due_cycle_started_at`).

Server-only: the cycle UUID and its start are set in the same write, under the
write lock, from one clock sample. A rename, quantity, tag or retry keeps both;
a new dated cycle (date, time or zone change, uncheck, add-restore, undo) gets a
new UUID and a new start; clearing the date clears both. Migration 17 backfills
existing dated items at one UTC instant without bumping any change sequence.
"""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from api_helpers import (
    add_item,
    changes,
    client_for,
    create_list,
    home,
    item_changed_seq,
    list_uid_of,
    new_id,
    op,
    send,
    write_locked,
)
from migration_helpers import migrate_to

import database_setup
from database_crud import (
    get_due_cycle_locked,
    restore_deleted_item_locked,
    update_item_details_locked,
)
from database_setup import db
from item_names import item_name_key
from reminders import due_schedule
from reminders.due_schedule import relative_rule_is_active

T0 = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)
T_10_10 = datetime(2026, 11, 4, 10, 10, tzinfo=UTC)
T_10_20 = datetime(2026, 11, 4, 10, 20, tzinfo=UTC)


class FakeCycleClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> FakeCycleClock:
    fake = FakeCycleClock(T0)
    monkeypatch.setattr(due_schedule, "cycle_clock", fake)
    return fake


@pytest.fixture
def item(clock):
    room_id, slug = home()
    list_id, _ = create_list("cycles", room_id)
    uid = add_item(list_id, "milk")
    return list_id, slug, uid, client_for(slug)


def stored(item_uid: str) -> dict:
    row = db.execute(
        "SELECT date, due_cycle, due_cycle_started_at FROM items WHERE uid = ?",
        (item_uid,),
    ).fetchone()
    return dict(zip(("date", "due_cycle", "due_cycle_started_at"), row, strict=True))


def edit_body(list_id, item_uid, **fields):
    body = {
        "op_id": new_id(),
        "type": "item.edit",
        "list_uid": list_uid_of(list_id),
        "item_uid": item_uid,
        "name": "milk",
        "description": "",
        "base_seq": item_changed_seq(item_uid),
    }
    body.update(fields)
    return body


def edit(item, **fields):
    list_id, slug, uid, client = item
    return op(client, slug, edit_body(list_id, uid, **fields))


def set_done(item, done: bool):
    list_id, slug, uid, client = item
    return op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.set_done",
            "list_uid": list_uid_of(list_id),
            "item_uid": uid,
            "done": done,
        },
    )


def timed_edit(item, date="2026-11-10", time="09:00", zone="Europe/Oslo", name="milk"):
    return edit(item, name=name, date=date, due_time=time, due_timezone=zone)


def test_dated_edit_starts_a_cycle_at_the_sampled_clock(item):
    _, _, uid, _ = item
    edit(item, date="2026-11-10")
    row = stored(uid)
    assert row["due_cycle"] is not None
    assert row["due_cycle_started_at"] == "2026-11-04T10:00:00.000Z"


def test_undated_item_has_no_cycle_or_start(item):
    _, _, uid, _ = item
    assert stored(uid) == {
        "date": None,
        "due_cycle": None,
        "due_cycle_started_at": None,
    }


def test_rename_keeps_the_cycle_and_its_start_when_the_clock_moved(item, clock):
    _, _, uid, _ = item
    edit(item, date="2026-11-10")
    before = stored(uid)
    clock.now = T_10_10
    edit(item, name="bread", date="2026-11-10")
    after = stored(uid)
    assert after["due_cycle"] == before["due_cycle"]
    assert after["due_cycle_started_at"] == "2026-11-04T10:00:00.000Z"


def test_quantity_and_description_edits_keep_the_cycle(item, clock):
    _, _, uid, _ = item
    edit(item, date="2026-11-10")
    before = stored(uid)
    clock.now = T_10_10
    edit(item, date="2026-11-10", description="2 litres", quantity=2)
    assert stored(uid) == before


def test_no_op_edit_and_retried_op_keep_the_start(item, clock):
    list_id, slug, uid, client = item
    edit(item, date="2026-11-10")
    before = stored(uid)
    clock.now = T_10_10
    body = edit_body(list_id, uid, date="2026-11-10")
    op(client, slug, body)
    clock.now = T_10_20
    replay = send(client, slug, body)
    assert replay.status_code == 200
    assert stored(uid) == before


def test_checking_keeps_the_cycle_and_unchecking_starts_a_new_one(item, clock):
    _, _, uid, _ = item
    timed_edit(item)
    before = stored(uid)
    clock.now = T_10_10
    set_done(item, True)
    assert stored(uid) == before
    clock.now = T_10_20
    set_done(item, False)
    after = stored(uid)
    assert after["due_cycle"] != before["due_cycle"]
    assert after["due_cycle_started_at"] == "2026-11-04T10:20:00.000Z"
    assert after["date"] == before["date"]


def test_unchecking_an_undated_item_keeps_no_cycle(item, clock):
    _, _, uid, _ = item
    set_done(item, True)
    set_done(item, False)
    assert stored(uid)["due_cycle_started_at"] is None


def test_add_restore_of_a_dated_checked_item_starts_a_new_cycle(item, clock):
    list_id, slug, uid, client = item
    timed_edit(item)
    set_done(item, True)
    clock.now = T_10_20
    response = op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.add",
            "list_uid": list_uid_of(list_id),
            "name": "milk",
        },
    )
    assert response["result"]["outcome"] == "restored"
    assert stored(uid)["due_cycle_started_at"] == "2026-11-04T10:20:00.000Z"


def test_undo_restore_of_a_dated_item_gets_a_new_start(item, clock):
    list_id, slug, _, client = item
    clock.now = T_10_20
    restored_uid = new_id()
    op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.restore",
            "list_uid": list_uid_of(list_id),
            "uid": restored_uid,
            "name": "eggs",
            "done": False,
            "tags": [],
            "description": "",
            "quantity": 1,
            "completed_at": None,
            "date": "2026-11-12",
            "due_time": "08:30",
            "due_timezone": "Europe/Oslo",
        },
    )
    row = stored(restored_uid)
    assert row["due_cycle_started_at"] == "2026-11-04T10:20:00.000Z"


def test_schedule_changes_start_a_new_cycle(item, clock):
    _, _, uid, _ = item
    timed_edit(item)
    first = stored(uid)
    clock.now = T_10_20
    timed_edit(item, time="10:00")  # time change
    second = stored(uid)
    assert second["due_cycle"] != first["due_cycle"]
    assert second["due_cycle_started_at"] == "2026-11-04T10:20:00.000Z"
    timed_edit(item, zone="Europe/Paris")  # zone change
    third = stored(uid)
    assert third["due_cycle"] != second["due_cycle"]
    edit(item, date="2026-11-11", due_time=None, due_timezone=None)  # time cleared
    assert stored(uid)["due_cycle_started_at"] == "2026-11-04T10:20:00.000Z"


def test_clearing_the_date_clears_the_cycle_and_its_start(item):
    _, _, uid, _ = item
    timed_edit(item)
    edit(item, date=None, due_time=None, due_timezone=None)
    assert stored(uid) == {
        "date": None,
        "due_cycle": None,
        "due_cycle_started_at": None,
    }


def test_setting_the_date_again_starts_a_new_cycle(item, clock):
    _, _, uid, _ = item
    edit(item, date="2026-11-10")
    edit(item, date=None)
    clock.now = T_10_20
    edit(item, date="2026-11-10")
    assert stored(uid)["due_cycle_started_at"] == "2026-11-04T10:20:00.000Z"


def test_date_only_items_use_the_same_cycle_start(item):
    _, _, uid, _ = item
    edit(item, date="2026-11-10")
    assert stored(uid)["due_cycle_started_at"] == "2026-11-04T10:00:00.000Z"
    assert stored(uid)["due_cycle"] is not None


def test_cycle_start_is_not_published_in_the_shared_feed(item):
    _, slug, uid, client = item
    timed_edit(item)
    [feed_item] = [i for i in changes(client, slug, 0)["items"] if i["uid"] == uid]
    assert "due_cycle" not in feed_item
    assert "due_cycle_started_at" not in feed_item


@pytest.mark.parametrize(
    "field",
    [
        {"due_cycle": "11111111-1111-4111-8111-111111111111"},
        {"due_cycle_started_at": "2026-11-04T09:00:00.000Z"},
    ],
)
def test_client_sent_cycle_fields_are_refused(item, field):
    list_id, slug, uid, client = item
    response = send(client, slug, edit_body(list_id, uid, date="2026-11-10", **field))
    assert response.status_code == 422


def test_failed_write_rolls_back_the_cycle_and_its_start(item, clock):
    list_id, _, uid, _ = item
    edit(item, date="2026-11-10")
    before = stored(uid)

    def change_then_fail():
        update_item_details_locked(
            write_id(uid),
            list_id,
            "milk",
            "",
            None,
            date_given=True,
            date="2026-11-20",
        )
        raise RuntimeError("fail after the cycle was written")

    clock.now = T_10_20
    with pytest.raises(RuntimeError):
        write_locked(change_then_fail)
    assert stored(uid) == before


def write_id(uid: str) -> int:
    return db.execute("SELECT id FROM items WHERE uid = ?", (uid,)).fetchone()[0]


def test_due_cycle_helper_exports_the_canonical_pair(item):
    _, _, uid, _ = item
    timed_edit(item)
    item_id = write_id(uid)
    assert get_due_cycle_locked(item_id) == {
        "cycle_id": stored(uid)["due_cycle"],
        "started_at": "2026-11-04T10:00:00.000Z",
    }
    edit(item, date=None, due_time=None, due_timezone=None)
    assert get_due_cycle_locked(item_id) is None


def test_restore_helper_gives_a_dated_restore_a_new_start(item, clock):
    list_id, _, _, _ = item
    clock.now = T_10_20
    write_locked(
        restore_deleted_item_locked,
        list_id,
        "bread",
        False,
        [],
        "",
        1,
        date="2026-11-14",
    )
    uid = db.execute("SELECT uid FROM items WHERE name = 'bread'").fetchone()[0]
    assert stored(uid)["due_cycle_started_at"] == "2026-11-04T10:20:00.000Z"


def test_frozen_ten_am_cycle_keeps_its_cutoff_across_a_rename(item, clock):
    # A 10:00 cycle change; a rename at 10:10 must not restart the cutoff.
    _, _, uid, _ = item
    edit(item, date="2026-11-10")
    clock.now = T_10_10
    edit(item, name="bread", date="2026-11-10")
    assert stored(uid)["due_cycle_started_at"] == "2026-11-04T10:00:00.000Z"


def test_cutoff_keeps_a_10_05_rule_and_suppresses_a_09_55_rule():
    # Cycle start 10:00. A rule due at 09:55 predates it; 10:05 does not.
    cycle_start = T0
    early = T0 - timedelta(minutes=5)
    later = T0 + timedelta(minutes=5)
    now = T0 + timedelta(minutes=30)
    assert now > later > cycle_start > early
    assert relative_rule_is_active(later, [cycle_start]) is True
    assert relative_rule_is_active(early, [cycle_start]) is False


def test_relative_cutoff_is_the_latest_applicable_activation():
    cycle_start = T0
    enrollment = T0 + timedelta(minutes=2)
    policy = T0 + timedelta(minutes=8)
    later = T0 + timedelta(minutes=9)
    assert relative_rule_is_active(later, [cycle_start, enrollment, policy]) is True
    assert relative_rule_is_active(later, [cycle_start, None, None]) is True
    earlier = T0 + timedelta(minutes=7)
    assert relative_rule_is_active(earlier, [cycle_start, enrollment, policy]) is False


class CountingUtcClock(datetime):
    """Stands in for database_setup.datetime: one fixed UTC instant, counted."""

    samples: list[datetime] = []  # noqa: RUF012 - reset per test by the fixture

    @classmethod
    def now(cls, tz=None):
        CountingUtcClock.samples.append(FIXED_MIGRATION_INSTANT)
        return FIXED_MIGRATION_INSTANT


FIXED_MIGRATION_INSTANT = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)


def test_migration_17_backfills_one_instant_without_a_change_seq_bump(
    tmp_path, monkeypatch
):
    connection = sqlite3.connect(tmp_path / "v16.db")
    migrate_to(connection, 16)
    connection.execute(
        "INSERT INTO lists (name, slug, room_id, share_token) "
        "VALUES ('Shop', 'shop', 1, 'token')"
    )
    for name, date in (("milk", "2026-10-18"), ("bread", "2026-10-19"), ("eggs", None)):
        connection.execute(
            "INSERT INTO items (name, name_key, done, list_id, date) "
            "VALUES (?, ?, 0, 1, ?)",
            (name, item_name_key(name), date),
        )
    connection.commit()
    seq_before = connection.execute(
        "SELECT change_seq FROM rooms WHERE id = 1"
    ).fetchone()
    item_seq_before = dict(
        connection.execute("SELECT name, changed_seq FROM items").fetchall()
    )
    cycles_before = dict(connection.execute("SELECT name, due_cycle FROM items"))

    CountingUtcClock.samples = []
    monkeypatch.setattr(database_setup, "datetime", CountingUtcClock)
    migrate_to(connection)
    monkeypatch.undo()

    # One clock sample for the whole migration, shared by every dated row.
    assert len(CountingUtcClock.samples) == 1
    starts = dict(
        connection.execute("SELECT name, due_cycle_started_at FROM items").fetchall()
    )
    assert starts == {
        "milk": "2026-11-04T10:00:00.000Z",
        "bread": "2026-11-04T10:00:00.000Z",
        "eggs": None,
    }
    assert (
        connection.execute("SELECT change_seq FROM rooms WHERE id = 1").fetchone()
        == seq_before
    )
    assert dict(connection.execute("SELECT name, changed_seq FROM items")) == (
        item_seq_before
    )
    assert dict(connection.execute("SELECT name, due_cycle FROM items")) == (
        cycles_before
    )
    connection.close()
