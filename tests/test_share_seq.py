"""Per-list seq for share links (decision 147, docs/change-tracking.md).

The share feed, the share op answers and the share stream all send the seq of
the shared list only. Other lists of the room do not move it.
"""

import asyncio
import sqlite3

import pytest
from api_helpers import (
    add_item,
    client_for,
    create_list,
    home,
    list_uid_of,
    new_id,
    op,
    write_locked,
)
from migration_helpers import migrate_to
from starlette.testclient import TestClient
from test_api_events import run
from test_api_share import public_client, share_changes, share_stream

import database_crud as crud
from database_setup import db, init_database


def _feed_seq(token: str) -> int:
    return share_changes(public_client(), token).json()["seq"]


def _room_seq(room_id: int) -> int:
    return crud.get_room_seq_locked(room_id)


def _share_post(token: str, body: dict) -> dict:
    client: TestClient = public_client()
    response = client.post(
        f"/api/v1/share/{token}/ops", json={"op_id": new_id(), **body}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _item_id(list_id: int, name: str) -> int:
    return db.execute(
        "SELECT id FROM items WHERE list_id = ? AND name = ?", (list_id, name)
    ).fetchone()[0]


def _age_deletions(uid: str) -> None:
    db.execute(
        "UPDATE deletions SET created_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now', "
        "'-91 days') WHERE uid = ?",
        (uid,),
    )
    db.commit()


@pytest.fixture
def shared():
    room_id, slug = home()
    list_id, _ = create_list("Groceries", room_id)
    add_item(list_id, "milk")
    other_id, _ = create_list("Private", room_id)
    add_item(other_id, "secret")
    token = db.execute(
        "SELECT share_token FROM lists WHERE id = ?", (list_id,)
    ).fetchone()[0]
    return {
        "room_id": room_id,
        "slug": slug,
        "list_id": list_id,
        "list_uid": list_uid_of(list_id),
        "other_id": other_id,
        "other_uid": list_uid_of(other_id),
        "token": token,
    }


def test_another_lists_changes_do_not_move_the_share_seq(shared):
    before = _feed_seq(shared["token"])
    room_before = _room_seq(shared["room_id"])

    add_item(shared["other_id"], "bread")

    assert _room_seq(shared["room_id"]) > room_before
    assert _feed_seq(shared["token"]) == before


def test_a_change_in_the_list_moves_the_share_seq(shared):
    before = _feed_seq(shared["token"])

    add_item(shared["list_id"], "eggs")

    seq = _feed_seq(shared["token"])
    assert seq > before
    assert (
        seq
        == db.execute(
            "SELECT changed_seq FROM items WHERE list_id = ? AND name = 'eggs'",
            (shared["list_id"],),
        ).fetchone()[0]
    )


def test_an_item_delete_in_the_list_moves_the_share_seq(shared):
    before = _feed_seq(shared["token"])
    item_id = _item_id(shared["list_id"], "milk")
    write_locked(crud.delete_item_locked, item_id, shared["list_id"])

    seq = _feed_seq(shared["token"])

    assert seq > before
    recorded = db.execute(
        "SELECT list_uid, changed_seq FROM deletions WHERE kind = 'item'"
    ).fetchone()
    assert recorded == (shared["list_uid"], seq)


def test_a_share_op_answer_seq_is_the_next_feed_seq(shared):
    answer = _share_post(
        shared["token"],
        {"type": "item.add", "list_uid": shared["list_uid"], "name": "tea"},
    )
    rejected = _share_post(
        shared["token"],
        {"type": "item.add", "list_uid": shared["list_uid"], "name": "milk"},
    )

    assert answer["status"] == "applied"
    assert rejected["status"] == "rejected"
    assert answer["seq"] == _feed_seq(shared["token"])
    assert rejected["seq"] == answer["seq"]


def test_the_share_seq_does_not_drop_when_its_deletions_are_pruned(shared):
    write_locked(
        crud.delete_item_locked, _item_id(shared["list_id"], "milk"), shared["list_id"]
    )
    before = _feed_seq(shared["token"])
    _age_deletions(db.execute("SELECT uid FROM deletions").fetchone()[0])

    assert crud.prune_deletions() == 1

    assert _feed_seq(shared["token"]) == before


def test_pruned_list_floors_are_dropped_with_the_list(shared):
    write_locked(
        crud.delete_item_locked, _item_id(shared["list_id"], "milk"), shared["list_id"]
    )
    _age_deletions(db.execute("SELECT uid FROM deletions").fetchone()[0])
    crud.prune_deletions()
    assert db.execute("SELECT COUNT(*) FROM share_seq_floors").fetchone()[0] == 1

    write_locked(crud.delete_list_locked, shared["list_id"])
    crud.prune_deletions()

    assert db.execute("SELECT COUNT(*) FROM share_seq_floors").fetchone()[0] == 0


def test_share_stream_is_quiet_for_other_lists_and_sends_its_own_seq(shared):
    room = client_for(shared["slug"])

    async def test() -> None:
        stream = share_stream(shared["token"])
        await stream.open()
        seq = _feed_seq(shared["token"])
        assert await stream.next_event() == ("seq", f'{{"seq": {seq}}}')

        await asyncio.to_thread(
            op,
            room,
            shared["slug"],
            {
                "op_id": new_id(),
                "type": "item.add",
                "list_uid": shared["other_uid"],
                "name": "bread",
            },
        )
        await stream.assert_quiet()

        await asyncio.to_thread(
            op,
            room,
            shared["slug"],
            {
                "op_id": new_id(),
                "type": "item.add",
                "list_uid": shared["list_uid"],
                "name": "eggs",
            },
        )
        event, data = await stream.next_event()
        assert (event, data) == ("seq", f'{{"seq": {_feed_seq(shared["token"])}}}')
        await stream.close()

    run(test)


def test_migration_records_the_list_of_new_deletions_only(tmp_path, monkeypatch):
    path = tmp_path / "v7.db"
    old = sqlite3.connect(path)
    migrate_to(old, 7)
    home_id = old.execute("SELECT id FROM rooms").fetchone()[0]
    old.execute(
        "INSERT INTO lists (id, name, slug, room_id, share_token) "
        "VALUES (1, 'Shop', 'shop', ?, 't1')",
        (home_id,),
    )
    old.execute("INSERT INTO items (id, name, done, list_id) VALUES (1, 'milk', 0, 1)")
    old.execute("DELETE FROM items WHERE id = 1")
    old.commit()
    old.close()

    monkeypatch.setenv("DB_PATH", str(path))
    connection = init_database()

    assert connection.execute("SELECT list_uid FROM deletions").fetchall() == [(None,)]
    connection.execute(
        "INSERT INTO items (id, name, done, list_id) VALUES (2, 'tea', 0, 1)"
    )
    connection.execute("DELETE FROM items WHERE id = 2")
    shop_uid = connection.execute("SELECT uid FROM lists WHERE id = 1").fetchone()[0]
    assert connection.execute(
        "SELECT list_uid FROM deletions WHERE uid != '' ORDER BY id DESC LIMIT 1"
    ).fetchone() == (shop_uid,)
    connection.execute("DELETE FROM lists WHERE id = 1")
    assert connection.execute(
        "SELECT kind, list_uid FROM deletions ORDER BY id DESC LIMIT 1"
    ).fetchone() == ("list", shop_uid)
    connection.close()
