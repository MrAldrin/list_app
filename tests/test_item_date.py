"""Items have an optional date: ISO text, NULL for none (migration 9, ops.py)."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing

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

from api.idempotency import request_hash
from api.ops import parse_op
from database_crud import restore_deleted_item_locked
from database_setup import db


@pytest.fixture
def dated_item():
    room_id, slug = home()
    list_id, _ = create_list("dates", room_id)
    milk_uid = add_item(list_id, "milk")
    return list_id, slug, milk_uid, client_for(slug)


def edit_body(list_id, item_uid, date=..., name="milk", **extra):
    body = {
        "op_id": new_id(),
        "type": "item.edit",
        "list_uid": list_uid_of(list_id),
        "item_uid": item_uid,
        "name": name,
        "description": "",
        "base_seq": item_changed_seq(item_uid),
        **extra,
    }
    if date is not ...:
        body["date"] = date
    return body


def edit(client, slug, list_id, item_uid, date=..., name="milk", **extra):
    return op(client, slug, edit_body(list_id, item_uid, date, name, **extra))


def stored_date(item_uid):
    return db.execute("SELECT date FROM items WHERE uid = ?", (item_uid,)).fetchone()[0]


def test_new_items_have_no_date(dated_item):
    _, _, milk_uid, _ = dated_item
    assert stored_date(milk_uid) is None


def test_edit_sets_a_date(dated_item):
    list_id, slug, milk_uid, client = dated_item
    response = edit(client, slug, list_id, milk_uid, "2026-10-18")
    assert response["status"] == "applied"
    assert stored_date(milk_uid) == "2026-10-18"


def test_edit_null_clears_the_date(dated_item):
    list_id, slug, milk_uid, client = dated_item
    edit(client, slug, list_id, milk_uid, "2026-10-18")
    response = edit(client, slug, list_id, milk_uid, None)
    assert response["status"] == "applied"
    assert stored_date(milk_uid) is None


def test_edit_without_date_field_keeps_the_date(dated_item):
    # An edit from a page that does not know about dates must not clear one.
    list_id, slug, milk_uid, client = dated_item
    edit(client, slug, list_id, milk_uid, "2026-10-18")
    response = edit(client, slug, list_id, milk_uid, name="oat milk")
    assert response["status"] == "applied"
    assert stored_date(milk_uid) == "2026-10-18"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "2026-1-5",
        "18/10/2026",
        "2026-10-18T00:00:00Z",
        " 2026-10-18",
        "20261018",
        "2026-02-30",
        "2026-13-01",
        "\uff12\uff10\uff12\uff16-10-18",
        20261018,
        True,
    ],
)
def test_invalid_date_is_rejected(dated_item, bad):
    list_id, slug, milk_uid, client = dated_item
    response = send(client, slug, edit_body(list_id, milk_uid, bad))
    assert response.status_code == 422
    assert stored_date(milk_uid) is None


def test_stale_date_change_is_refused(dated_item):
    # Another device changed the item after this page loaded; this page wants
    # a different date, so its save is refused and nothing changes.
    list_id, slug, milk_uid, client = dated_item
    base_seq = item_changed_seq(milk_uid)
    edit(client, slug, list_id, milk_uid, "2026-10-18")
    response = op(
        client,
        slug,
        {
            "op_id": new_id(),
            "type": "item.edit",
            "list_uid": list_uid_of(list_id),
            "item_uid": milk_uid,
            "name": "milk",
            "description": "",
            "date": "2026-11-01",
            "base_seq": base_seq,
        },
    )
    assert (response["status"], response["code"]) == ("rejected", "changed_meanwhile")
    assert stored_date(milk_uid) == "2026-10-18"


def test_date_is_in_the_changes_feed(dated_item):
    list_id, slug, milk_uid, client = dated_item
    edit(client, slug, list_id, milk_uid, "2026-10-18")
    feed = changes(client, slug, 0)
    (item,) = [row for row in feed["items"] if row["uid"] == milk_uid]
    assert item["date"] == "2026-10-18"


def test_undo_restores_the_date(dated_item):
    list_id, slug, _, client = dated_item
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
    assert stored_date(restored_uid) == "2026-10-20"


def test_restore_without_date_has_none(dated_item):
    list_id, slug, _, client = dated_item
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
        },
    )
    assert response["status"] == "applied"
    assert stored_date(restored_uid) is None


def test_edit_without_date_keeps_its_old_hash():
    # Ops stored before the date field hashed without it; their retries must
    # still match. A null date is left out of the hash, as for other new fields.
    body = {
        "op_id": new_id(),
        "type": "item.edit",
        "list_uid": new_id(),
        "item_uid": new_id(),
        "name": "milk",
        "description": "",
        "quantity": 2,
        "base_seq": 3,
    }
    old_shape = parse_op(body).model_dump(mode="json")
    old_shape.pop("date")
    canonical = json.dumps(
        old_shape, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert (
        request_hash(parse_op(body)) == hashlib.sha256(canonical.encode()).hexdigest()
    )


def test_restore_helper_stores_the_date(dated_item):
    list_id, _, _, _ = dated_item
    item_id = write_locked(
        restore_deleted_item_locked,
        list_id,
        "bread",
        False,
        [],
        "",
        1,
        date="2026-12-24",
    )
    assert db.execute("SELECT date FROM items WHERE id = ?", (item_id,)).fetchone()[
        0
    ] == ("2026-12-24")


@pytest.fixture
def migrated() -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(":memory:")) as connection, connection:
        migrate_to(connection, version=8)
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


def test_migration_adds_nullable_date_and_keeps_rows(migrated):
    migrate_to(migrated)
    assert migrated.execute(
        "SELECT date FROM items WHERE name = 'milk'"
    ).fetchone() == (None,)


@pytest.mark.parametrize("value", ["2026-1-5", "18/10/2026", 20261018, "2026-10-18 "])
def test_database_rejects_a_malformed_date(migrated, value):
    migrate_to(migrated)
    with pytest.raises(sqlite3.IntegrityError, match="YYYY-MM-DD"):
        migrated.execute("UPDATE items SET date = ? WHERE name = 'milk'", (value,))
    with pytest.raises(sqlite3.IntegrityError, match="YYYY-MM-DD"):
        migrated.execute(
            "INSERT INTO items (name, done, list_id, date) VALUES ('eggs', 0, 1, ?)",
            (value,),
        )


def test_database_accepts_a_date_and_null(migrated):
    migrate_to(migrated)
    migrated.execute("UPDATE items SET date = '2026-10-18' WHERE name = 'milk'")
    migrated.execute("UPDATE items SET date = NULL WHERE name = 'milk'")
    assert migrated.execute(
        "SELECT date FROM items WHERE name = 'milk'"
    ).fetchone() == (None,)
