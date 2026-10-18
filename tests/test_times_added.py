"""Items count how often they were added, and when last (migration 10, ops.py).

Adding, restoring a checked item and unchecking count. Checking, edits, undo
of a delete (which keeps the count it had) and repeated unchecks do not.
"""

import sqlite3
from collections.abc import Iterator

import pytest
from api_helpers import (
    changes,
    client_for,
    default_list,
    home,
    item_changed_seq,
    new_id,
    op,
    send,
    write_locked,
)
from migration_helpers import migrate_to

from database_setup import db

OLD_TIME = "2000-01-01T00:00:00.000Z"


@pytest.fixture
def shop():
    room_id, slug = home()
    list_id, list_uid = default_list()
    return room_id, list_id, list_uid, slug, client_for(slug)


def stored(item_uid):
    """(add_count, added_at) as the database has them."""
    return db.execute(
        "SELECT add_count, added_at FROM items WHERE uid = ?", (item_uid,)
    ).fetchone()


def backdate(item_uid):
    """Give the item an old added_at, so a later add is visibly newer."""
    write_locked(
        db.execute,
        "UPDATE items SET added_at = ? WHERE uid = ?",
        (OLD_TIME, item_uid),
    )


def add(client, slug, list_uid, name):
    return op(
        client,
        slug,
        {"op_id": new_id(), "type": "item.add", "list_uid": list_uid, "name": name},
    )


def set_done(client, slug, list_uid, item_uid, done):
    return op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.set_done",
            "list_uid": list_uid,
            "item_uid": item_uid,
            "done": done,
        },
    )


def edit(client, slug, list_uid, item_uid):
    return op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.edit",
            "list_uid": list_uid,
            "item_uid": item_uid,
            "name": "milk",
            "description": "lactose free",
            "base_seq": item_changed_seq(item_uid),
        },
    )


def test_a_new_item_counts_once_and_has_a_time(shop):
    _, _, list_uid, slug, client = shop
    response = add(client, slug, list_uid, "milk")
    assert response["result"]["outcome"] == "added"
    count, added_at = stored(response["result"]["item_uid"])
    assert count == 1
    assert added_at.endswith("Z")


def test_adding_a_checked_item_again_counts(shop):
    _, _, list_uid, slug, client = shop
    milk_uid = add(client, slug, list_uid, "milk")["result"]["item_uid"]
    set_done(client, slug, list_uid, milk_uid, True)
    backdate(milk_uid)
    response = add(client, slug, list_uid, "milk")
    assert response["result"] == {
        "item_uid": milk_uid,
        "outcome": "restored",
        "changed_seq": item_changed_seq(milk_uid),
    }
    count, added_at = stored(milk_uid)
    assert count == 2
    assert added_at != OLD_TIME


def test_adding_an_active_item_again_does_not_count(shop):
    _, _, list_uid, slug, client = shop
    milk_uid = add(client, slug, list_uid, "milk")["result"]["item_uid"]
    backdate(milk_uid)
    response = send(
        client,
        slug,
        {"op_id": new_id(), "type": "item.add", "list_uid": list_uid, "name": "milk"},
    )
    assert response.json()["status"] == "rejected"
    assert stored(milk_uid) == (1, OLD_TIME)


def test_unchecking_counts(shop):
    _, _, list_uid, slug, client = shop
    milk_uid = add(client, slug, list_uid, "milk")["result"]["item_uid"]
    set_done(client, slug, list_uid, milk_uid, True)
    backdate(milk_uid)
    set_done(client, slug, list_uid, milk_uid, False)
    count, added_at = stored(milk_uid)
    assert count == 2
    assert added_at != OLD_TIME


def test_unchecking_an_unchecked_item_does_not_count(shop):
    _, _, list_uid, slug, client = shop
    milk_uid = add(client, slug, list_uid, "milk")["result"]["item_uid"]
    backdate(milk_uid)
    set_done(client, slug, list_uid, milk_uid, False)
    assert stored(milk_uid) == (1, OLD_TIME)


def test_checking_does_not_count(shop):
    _, _, list_uid, slug, client = shop
    milk_uid = add(client, slug, list_uid, "milk")["result"]["item_uid"]
    backdate(milk_uid)
    set_done(client, slug, list_uid, milk_uid, True)
    assert stored(milk_uid) == (1, OLD_TIME)


def test_editing_does_not_count(shop):
    _, _, list_uid, slug, client = shop
    milk_uid = add(client, slug, list_uid, "milk")["result"]["item_uid"]
    backdate(milk_uid)
    edit(client, slug, list_uid, milk_uid)
    assert stored(milk_uid) == (1, OLD_TIME)


def test_quantity_and_tags_do_not_count(shop):
    _, _, list_uid, slug, client = shop
    milk_uid = add(client, slug, list_uid, "milk")["result"]["item_uid"]
    backdate(milk_uid)
    op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.quantity_delta",
            "list_uid": list_uid,
            "item_uid": milk_uid,
            "delta": 2,
        },
    )
    op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.toggle_tag",
            "list_uid": list_uid,
            "item_uid": milk_uid,
            "tag": "Lidl",
        },
    )
    assert stored(milk_uid) == (1, OLD_TIME)


def test_a_retried_add_counts_once(shop):
    # Offline sync sends an op again with the same op_id: it must not count twice.
    _, _, list_uid, slug, client = shop
    milk_uid = add(client, slug, list_uid, "milk")["result"]["item_uid"]
    set_done(client, slug, list_uid, milk_uid, True)
    body = {"op_id": new_id(), "type": "item.add", "list_uid": list_uid, "name": "milk"}
    first = op(client, slug, body)
    again = op(client, slug, body)
    assert first == again
    assert stored(milk_uid)[0] == 2


def restore_body(list_uid, **fields):
    return {
        "op_id": new_id(),
        "type": "item.restore",
        "list_uid": list_uid,
        "name": "eggs",
        "done": False,
        "tags": [],
        "description": "",
        "quantity": 1,
        "completed_at": None,
        **fields,
    }


def test_undo_of_a_delete_keeps_the_count_it_had(shop):
    _, _, list_uid, slug, client = shop
    eggs_uid = add(client, slug, list_uid, "eggs")["result"]["item_uid"]
    add(client, slug, list_uid, "eggs")  # rejected: already active, no count
    set_done(client, slug, list_uid, eggs_uid, True)
    add(client, slug, list_uid, "eggs")  # restored: count 2
    count, added_at = stored(eggs_uid)
    op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.delete",
            "list_uid": list_uid,
            "item_uid": eggs_uid,
        },
    )
    restored_uid = new_id()
    response = op(
        client,
        slug,
        restore_body(list_uid, uid=restored_uid, add_count=count, added_at=added_at),
    )
    assert response["status"] == "applied"
    assert stored(restored_uid) == (count, added_at)


def test_restore_keeps_a_time_written_without_milliseconds(shop):
    _, _, list_uid, slug, client = shop
    restored_uid = new_id()
    response = op(
        client,
        slug,
        restore_body(
            list_uid,
            uid=restored_uid,
            add_count=4,
            added_at="2026-10-01T10:00:00Z",
        ),
    )
    assert response["status"] == "applied"
    assert stored(restored_uid) == (4, "2026-10-01T10:00:00.000Z")


@pytest.mark.parametrize(
    "fields",
    [
        {"add_count": 0},
        {"add_count": 1.5},
        {"add_count": True},
        {"added_at": "yesterday"},
        {"added_at": 20261001},
    ],
)
def test_bad_count_or_time_is_rejected(shop, fields):
    _, _, list_uid, slug, client = shop
    response = send(client, slug, restore_body(list_uid, uid=new_id(), **fields))
    assert response.status_code == 422


def test_count_and_time_are_in_the_changes_feed(shop):
    _, _, list_uid, slug, client = shop
    milk_uid = add(client, slug, list_uid, "milk")["result"]["item_uid"]
    set_done(client, slug, list_uid, milk_uid, True)
    add(client, slug, list_uid, "milk")
    feed = changes(client, slug, 0)
    (item,) = [row for row in feed["items"] if row["uid"] == milk_uid]
    count, added_at = stored(milk_uid)
    assert count == 2
    assert (item["add_count"], item["added_at"]) == (2, added_at)


@pytest.fixture
def migrated() -> Iterator[sqlite3.Connection]:
    with sqlite3.connect(":memory:") as connection:
        migrate_to(connection, version=9)
        # Migration 1 creates the room "Home" with ID 1.
        connection.execute(
            "INSERT INTO lists (name, slug, room_id, share_token) "
            "VALUES ('Shop', 'shop', 1, 'token')"
        )
        connection.execute(
            "INSERT INTO items (name, done, list_id) VALUES ('milk', 0, 1)"
        )
        connection.commit()
        yield connection


def test_migration_counts_existing_items_once_without_a_time(migrated):
    migrate_to(migrated)
    assert migrated.execute(
        "SELECT add_count, added_at FROM items WHERE name = 'milk'"
    ).fetchone() == (1, None)


def test_migration_keeps_change_tracking(migrated):
    migrate_to(migrated)
    before = migrated.execute("SELECT change_seq FROM rooms WHERE id = 1").fetchone()
    migrated.execute("UPDATE items SET add_count = 2 WHERE name = 'milk'")
    after = migrated.execute("SELECT change_seq FROM rooms WHERE id = 1").fetchone()
    assert after[0] == before[0] + 1


@pytest.mark.parametrize("value", [0, -1])
def test_database_rejects_a_count_below_one(migrated, value):
    migrate_to(migrated)
    with pytest.raises(sqlite3.IntegrityError, match="add_count"):
        migrated.execute("UPDATE items SET add_count = ? WHERE name = 'milk'", (value,))
    with pytest.raises(sqlite3.IntegrityError, match="add_count"):
        migrated.execute(
            "INSERT INTO items (name, done, list_id, add_count) VALUES ('eggs', 0, 1, ?)",
            (value,),
        )
