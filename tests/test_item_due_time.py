"""Items can have a shared due time and zone (migration 15, reminders/due_schedule.py).

Covers absent/null/legacy semantics, the server-computed UTC `due_at`, due-cycle
identity, restore roundtrips and the request hash for the new optional fields.
"""

import sqlite3

import pytest
from api_helpers import (
    add_item,
    assert_error,
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
from migration_helpers import LATEST_VERSION, migrate_to

from api.idempotency import request_hash
from api.ops import parse_op
from database_crud import restore_deleted_item_locked
from database_setup import db
from item_names import item_name_key


@pytest.fixture
def item():
    room_id, slug = home()
    list_id, _ = create_list("due", room_id)
    uid = add_item(list_id, "milk")
    return list_id, slug, uid, client_for(slug)


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


DUE_COLUMNS = ("date", "due_time", "due_timezone", "due_at", "due_cycle")


def stored(item_uid):
    row = db.execute(
        f"SELECT {', '.join(DUE_COLUMNS)} FROM items WHERE uid = ?", (item_uid,)
    ).fetchone()
    return dict(zip(DUE_COLUMNS, row))


def feed_item(client, slug, item_uid):
    """The item as the full changes feed sends it."""
    [item] = [i for i in changes(client, slug, 0)["items"] if i["uid"] == item_uid]
    return item


def timed_edit(item, date, time, zone, name="milk"):
    list_id, slug, uid, client = item
    return op(
        client,
        slug,
        edit_body(
            list_id,
            uid,
            name=name,
            date=date,
            due_time=time,
            due_timezone=zone,
        ),
    )


def test_timed_edit_stores_the_zone_and_resolves_utc(item):
    _, _, uid, _ = item
    response = timed_edit(item, "2026-03-29", "02:30", "Europe/Oslo")
    assert response["status"] == "applied"
    row = stored(uid)
    assert row["date"] == "2026-03-29"
    assert row["due_time"] == "02:30"
    assert row["due_timezone"] == "Europe/Oslo"
    # The gap resolves to 03:00 CEST, i.e. 01:00 UTC.
    assert row["due_at"] == "2026-03-29T01:00:00.000Z"
    assert row["due_cycle"] is not None


def test_timed_edit_without_a_zone_is_rejected_and_stores_nothing(item):
    _, _, uid, _ = item
    response = timed_edit(item, "2026-10-18", "09:00", None)
    assert (response["status"], response["code"]) == ("rejected", "invalid_due")
    assert stored(uid)["date"] is None


def test_unknown_zone_is_rejected_safely(item):
    _, _, uid, _ = item
    response = timed_edit(item, "2026-10-18", "09:00", "Nope/Zone")
    assert (response["status"], response["code"]) == (
        "rejected",
        "time_zone_unavailable",
    )
    assert stored(uid)["date"] is None


def test_client_due_at_is_refused(item):
    list_id, slug, uid, client = item
    response = send(
        client,
        slug,
        edit_body(
            list_id,
            uid,
            date="2026-10-18",
            due_time="09:00",
            due_timezone="Europe/Oslo",
            due_at="2026-10-18T07:00:00.000Z",
        ),
    )
    assert response.status_code == 422


def test_legacy_date_only_edit_keeps_the_stored_time_and_zone(item):
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    stored_before = stored(uid)
    response = op(
        client,
        slug,
        edit_body(list_id, uid, name="milk", date="2026-10-19"),
    )
    assert response["status"] == "applied"
    row = stored(uid)
    assert row["date"] == "2026-10-19"
    assert (row["due_time"], row["due_timezone"]) == ("09:00", "Europe/Oslo")
    # The UTC instant follows the new date, from the kept wall time and zone.
    assert row["due_at"] == "2026-10-19T07:00:00.000Z"
    assert row["due_cycle"] != stored_before["due_cycle"]


def test_clearing_the_date_clears_time_and_zone(item):
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    response = op(client, slug, edit_body(list_id, uid, date=None))
    assert response["status"] == "applied"
    assert stored(uid) == {
        "date": None,
        "due_time": None,
        "due_timezone": None,
        "due_at": None,
        "due_cycle": None,
    }


def test_clearing_the_time_returns_to_date_only(item):
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    response = op(
        client, slug, edit_body(list_id, uid, due_time=None, due_timezone=None)
    )
    assert response["status"] == "applied"
    row = stored(uid)
    assert row["date"] == "2026-10-18"
    assert (row["due_time"], row["due_timezone"], row["due_at"]) == (None, None, None)


def test_name_edit_keeps_the_due_cycle_and_utc(item):
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    before = stored(uid)
    op(client, slug, edit_body(list_id, uid, name="oat milk"))
    after = stored(uid)
    assert after["due_cycle"] == before["due_cycle"]
    assert after["due_at"] == before["due_at"]


def test_zone_change_recomputes_utc_and_starts_a_new_cycle(item):
    _, _, uid, _ = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    before = stored(uid)
    timed_edit(item, "2026-10-18", "09:00", "UTC")
    after = stored(uid)
    assert after["due_at"] == "2026-10-18T09:00:00.000Z"
    assert after["due_cycle"] != before["due_cycle"]


def test_checking_then_unchecking_starts_a_new_cycle_only_when_dated(item):
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    before = stored(uid)["due_cycle"]
    op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.set_done",
            "list_uid": list_uid_of(list_id),
            "item_uid": uid,
            "done": True,
        },
    )
    assert stored(uid)["due_cycle"] == before  # Checking alone keeps the cycle.
    op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.set_done",
            "list_uid": list_uid_of(list_id),
            "item_uid": uid,
            "done": False,
        },
    )
    assert stored(uid)["due_cycle"] != before  # Unchecking starts a new one.


def test_add_restore_of_a_dated_checked_item_starts_a_new_cycle(item):
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    before = stored(uid)["due_cycle"]
    op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.set_done",
            "list_uid": list_uid_of(list_id),
            "item_uid": uid,
            "done": True,
        },
    )
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
    assert stored(uid)["due_cycle"] != before


def test_undo_restores_the_time_zone_and_recomputes_utc(item):
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-25", "02:30", "Europe/Oslo")
    row = stored(uid)
    op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.delete",
            "list_uid": list_uid_of(list_id),
            "item_uid": uid,
        },
    )
    restored_uid = new_id()
    response = op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.restore",
            "list_uid": list_uid_of(list_id),
            "uid": restored_uid,
            "name": "milk",
            "done": False,
            "tags": [],
            "description": "",
            "quantity": 1,
            "completed_at": None,
            "date": "2026-10-25",
            "due_time": "02:30",
            "due_timezone": "Europe/Oslo",
        },
    )
    assert response["status"] == "applied"
    restored = stored(restored_uid)
    assert (restored["due_time"], restored["due_timezone"]) == ("02:30", "Europe/Oslo")
    # Fall-back day, 02:30 occurs twice: the first occurrence is CEST.
    assert restored["due_at"] == row["due_at"] == "2026-10-25T00:30:00.000Z"
    assert restored["due_cycle"] is not None


def test_restore_without_time_fields_is_date_only(item):
    list_id, slug, _, client = item
    restored_uid = new_id()
    response = op(
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
            "date": "2026-10-20",
        },
    )
    assert response["status"] == "applied"
    row = stored(restored_uid)
    assert (row["due_time"], row["due_timezone"], row["due_at"]) == (None, None, None)
    assert row["due_cycle"] is not None


def test_restore_rejects_a_time_without_a_date(item):
    list_id, slug, _, client = item
    response = op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.restore",
            "list_uid": list_uid_of(list_id),
            "name": "eggs",
            "done": False,
            "tags": [],
            "description": "",
            "quantity": 1,
            "completed_at": None,
            "due_time": "09:00",
            "due_timezone": "Europe/Oslo",
        },
    )
    assert (response["status"], response["code"]) == ("rejected", "invalid_due")


def test_feed_publishes_the_due_fields_with_the_utc_instant(item):
    _, slug, uid, client = item
    timed_edit(item, "2026-03-29", "02:30", "Europe/Oslo")
    feed = feed_item(client, slug, uid)
    assert (feed["due_time"], feed["due_timezone"]) == ("02:30", "Europe/Oslo")
    assert feed["due_at"] == "2026-03-29T01:00:00.000Z"


def test_explicit_null_due_time_hashes_differently_from_absent():
    base = {
        "op_id": new_id(),
        "type": "item.edit",
        "list_uid": new_id(),
        "item_uid": new_id(),
        "name": "milk",
        "description": "",
        "base_seq": 3,
        "date": "2026-10-18",
    }
    absent = request_hash(parse_op(base))
    explicit_null = request_hash(parse_op({**base, "due_time": None}))
    assert absent != explicit_null


def test_legacy_edit_hash_without_due_fields_is_unchanged():
    # Literal hash of an edit stored before due_time/due_timezone existed
    # (computed from the code before this change). A retry must still match.
    body = {
        "op_id": "11111111-1111-4111-8111-111111111111",
        "type": "item.edit",
        "list_uid": "22222222-2222-4222-8222-222222222222",
        "item_uid": "33333333-3333-4333-8333-333333333333",
        "name": "Milk",
        "description": "",
        "base_seq": 5,
        "date": "2026-03-29",
    }
    expected = "9e19fefc081eb24a30d7733eaae166c1a625e199b663c9a6099a293628e9633e"
    assert request_hash(parse_op(body)) == expected


# Literal hashes of ops stored before the due fields (and before date for
# restore/set_done). Computed from the code before this change; a retry must
# still match these exactly.
LEGACY_HASHES = {
    "item.restore": (
        {
            "op_id": "11111111-1111-4111-8111-111111111111",
            "type": "item.restore",
            "list_uid": "22222222-2222-4222-8222-222222222222",
            "name": "Milk",
            "done": False,
            "tags": ["a"],
            "description": "",
            "quantity": 2,
            "completed_at": None,
        },
        "793dfd767bf2485a426d1dd7a3fa662206ab6f5bf0a8dab1766e5573496631e1",
    ),
    "item.restore.dated": (
        {
            "op_id": "11111111-1111-4111-8111-111111111111",
            "type": "item.restore",
            "list_uid": "22222222-2222-4222-8222-222222222222",
            "name": "Milk",
            "done": True,
            "tags": [],
            "description": "x",
            "quantity": 1,
            "completed_at": "2026-01-02T03:04:05Z",
            "date": "2026-05-01",
            "add_count": 3,
            "added_at": "2026-01-01T00:00:00.000Z",
        },
        "5431825885e66e9a5a6cb6725e3d86b6edce7670d3e10d848588bad6e9553acd",
    ),
    "item.set_done": (
        {
            "op_id": "11111111-1111-4111-8111-111111111111",
            "type": "item.set_done",
            "list_uid": "22222222-2222-4222-8222-222222222222",
            "item_uid": "33333333-3333-4333-8333-333333333333",
            "done": True,
        },
        "9a8411ce58fc112f992b37d3d11d4e60ffac58748881e686d50806f38e607688",
    ),
    "item.edit.null_date": (
        {
            "op_id": "11111111-1111-4111-8111-111111111111",
            "type": "item.edit",
            "list_uid": "22222222-2222-4222-8222-222222222222",
            "item_uid": "33333333-3333-4333-8333-333333333333",
            "name": "Milk",
            "description": "",
            "base_seq": 5,
            "date": None,
        },
        "0d965b7676140b960320bc22fd5aa84aa20b8633bfbd3554c0438a3b32163e64",
    ),
}


@pytest.mark.parametrize("name", sorted(LEGACY_HASHES))
def test_legacy_op_hashes_are_unchanged(name):
    body, expected = LEGACY_HASHES[name]
    assert request_hash(parse_op(body)) == expected


def test_explicit_null_due_time_on_restore_hashes_differently_from_absent():
    body, _ = LEGACY_HASHES["item.restore"]
    absent = request_hash(parse_op(body))
    explicit_null = request_hash(
        parse_op({**body, "due_time": None, "due_timezone": None})
    )
    assert absent != explicit_null


def test_database_refuses_a_time_without_a_zone(item):
    _, _, uid, _ = item
    with pytest.raises(sqlite3.IntegrityError, match="must go together"):
        db.execute(
            "UPDATE items SET date = '2026-10-18', due_time = '09:00' WHERE uid = ?",
            (uid,),
        )


def test_database_refuses_a_due_time_without_a_date(item):
    _, _, uid, _ = item
    with pytest.raises(sqlite3.IntegrityError, match="must go together"):
        db.execute(
            "UPDATE items SET due_time = '09:00', due_timezone = 'UTC', "
            "due_at = '2026-10-18T09:00:00.000Z' WHERE uid = ?",
            (uid,),
        )


def test_restore_helper_rejects_an_invalid_schedule_without_writing(item):
    list_id, _, _, _ = item
    with pytest.raises(ValueError):
        write_locked(
            restore_deleted_item_locked,
            list_id,
            "bread",
            False,
            [],
            "",
            1,
            date=None,
            due_time="09:00",
            due_timezone="UTC",
        )
    assert (
        db.execute("SELECT COUNT(*) FROM items WHERE name = 'bread'").fetchone()[0] == 0
    )


def test_migration_fifteen_backfills_cycles_without_a_change_seq_bump(tmp_path):
    connection = sqlite3.connect(tmp_path / "v14.db")
    migrate_to(connection, LATEST_VERSION - 1)
    connection.execute(
        "INSERT INTO lists (name, slug, room_id, share_token) "
        "VALUES ('Shop', 'shop', 1, 'token')"
    )
    for name, date in (("milk", "2026-10-18"), ("eggs", None)):
        connection.execute(
            "INSERT INTO items (name, name_key, done, list_id, date) "
            "VALUES (?, ?, 0, 1, ?)",
            (name, item_name_key(name), date),
        )
    connection.commit()
    seq_before = connection.execute(
        "SELECT change_seq FROM rooms WHERE id = 1"
    ).fetchone()
    migrate_to(connection)
    cycles = dict(connection.execute("SELECT name, due_cycle FROM items").fetchall())
    assert len(cycles["milk"]) == 36
    assert cycles["eggs"] is None
    assert (
        connection.execute("SELECT change_seq FROM rooms WHERE id = 1").fetchone()
        == seq_before
    )


def test_timed_check_and_uncheck_keep_the_source_zone_and_utc(item):
    # Check and uncheck change only the cycle: the wall time, zone and the
    # server-computed UTC instant stay the same.
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    before = stored(uid)
    for done in (True, False):
        op(
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
        after = stored(uid)
        assert (after["date"], after["due_time"], after["due_timezone"]) == (
            "2026-10-18",
            "09:00",
            "Europe/Oslo",
        )
        assert after["due_at"] == before["due_at"] == "2026-10-18T07:00:00.000Z"
    assert after["due_cycle"] != before["due_cycle"]


def test_add_restore_keeps_the_source_zone_and_utc(item):
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    before = stored(uid)
    op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.set_done",
            "list_uid": list_uid_of(list_id),
            "item_uid": uid,
            "done": True,
        },
    )
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
    after = stored(uid)
    assert (after["due_time"], after["due_timezone"], after["due_at"]) == (
        "09:00",
        "Europe/Oslo",
        before["due_at"],
    )
    assert after["due_cycle"] != before["due_cycle"]


def test_unknown_zone_on_a_time_only_edit_keeps_the_stored_schedule(item):
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    before = stored(uid)
    response = op(
        client,
        slug,
        edit_body(list_id, uid, due_timezone="Nope/Zone"),
    )
    assert (response["status"], response["code"]) == (
        "rejected",
        "time_zone_unavailable",
    )
    assert stored(uid) == before


@pytest.mark.parametrize("bad_time", ["9:00", "25:00", "09:60", "09:00:00", "noon"])
def test_malformed_due_time_is_a_422_and_changes_nothing(item, bad_time):
    list_id, slug, uid, client = item
    timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    before = stored(uid)
    response = send(
        client,
        slug,
        edit_body(
            list_id,
            uid,
            name="oat milk",
            date="2026-10-19",
            due_time=bad_time,
            due_timezone="Europe/Oslo",
        ),
    )
    assert_error(response, 422, "invalid_request")
    assert stored(uid) == before
    [item_row] = [row for row in changes(client, slug, 0)["items"] if row["uid"] == uid]
    assert item_row["name"] == "milk"


def test_malformed_due_time_on_restore_is_a_422_and_restores_nothing(item):
    list_id, slug, _, client = item
    response = send(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.restore",
            "list_uid": list_uid_of(list_id),
            "name": "eggs",
            "done": False,
            "tags": [],
            "description": "",
            "quantity": 1,
            "completed_at": None,
            "date": "2026-10-18",
            "due_time": "9:00",
            "due_timezone": "Europe/Oslo",
        },
    )
    assert response.status_code == 422
    assert (
        db.execute("SELECT COUNT(*) FROM items WHERE name = 'eggs'").fetchone()[0] == 0
    )


def test_missing_zone_data_is_refused_without_touching_shared_state(item, monkeypatch):
    # Simulate a server without the zone's data. Only the name lookup inside
    # reminders.zoned_time fails: ZoneInfo's cache and the other zones stay as
    # they were, so later tests and requests are not affected.
    from zoneinfo import ZoneInfo as RealZoneInfo

    import reminders.zoned_time as zoned_time

    def no_data(key):
        if key == "Europe/Oslo":
            raise zoned_time.ZoneInfoNotFoundError(key)
        return RealZoneInfo(key)

    list_id, slug, uid, client = item
    monkeypatch.setattr(zoned_time, "ZoneInfo", no_data)
    response = timed_edit(item, "2026-10-18", "09:00", "Europe/Oslo")
    assert (response["status"], response["code"]) == (
        "rejected",
        "time_zone_unavailable",
    )
    assert stored(uid)["date"] is None
    # Date-only and unchanged-schedule renames still work without zone data.
    assert op(client, slug, edit_body(list_id, uid, date="2026-10-20"))["status"] == (
        "applied"
    )
    assert op(client, slug, edit_body(list_id, uid, name="oat milk"))["status"] == (
        "applied"
    )
    monkeypatch.undo()
    assert RealZoneInfo("Europe/Oslo").key == "Europe/Oslo"
