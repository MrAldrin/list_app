"""Count limits: how many items, lists, tags and sessions may exist.

Limits are in src/field_limits.py. Refused writes answer with the `too_many`
code (docs/api.md, rejection codes). Sessions are not refused: a new sign-in
drops the room's oldest sessions.
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from api_helpers import (
    add_list_tag,
    default_list,
    home,
    new_id,
    op,
    update_list_tags_settings,
    write_locked,
)

import database_crud
from database_crud import (
    _DB_LOCK,
    CountLimitReached,
    _insert_room_access_token_locked,
    _valid_room_id_for_token_locked,
    authenticate_room_and_issue_token,
    change_list_tag_locked,
    create_or_find_list_locked,
    restore_deleted_item_locked,
)
from database_setup import db
from field_limits import (
    MAX_ITEMS_PER_LIST,
    MAX_LISTS_PER_ROOM,
    MAX_SESSIONS_PER_ROOM,
    MAX_TAGS_PER_LIST,
)


def _item_count(list_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM items WHERE list_id = ?", (list_id,)
    ).fetchone()[0]


def _list_count(room_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM lists WHERE room_id = ?", (room_id,)
    ).fetchone()[0]


def _fill_items(list_id: int, count: int) -> None:
    db.executemany(
        "INSERT INTO items (name, done, list_id, uid) VALUES (?, 0, ?, NULL)",
        [(f"item {number}", list_id) for number in range(count)],
    )
    db.commit()


def _fill_lists(room_id: int, count: int) -> None:
    db.executemany(
        "INSERT INTO lists (name, slug, room_id, share_token) VALUES (?, ?, ?, ?)",
        [
            (
                f"list {number}",
                f"filler-{number}-{uuid.uuid4().hex[:8]}",
                room_id,
                str(uuid.uuid4()),
            )
            for number in range(count)
        ],
    )
    db.commit()


def test_the_limits_are_the_agreed_numbers():
    assert MAX_ITEMS_PER_LIST == 1000
    assert MAX_LISTS_PER_ROOM == 100
    assert MAX_TAGS_PER_LIST == 50
    assert MAX_SESSIONS_PER_ROOM == 200


# Items per list


def test_adding_an_item_is_refused_when_the_list_is_full():
    list_id, _ = default_list()
    _fill_items(list_id, MAX_ITEMS_PER_LIST)
    with pytest.raises(CountLimitReached, match="at most 1000 items"):
        write_locked(database_crud.add_or_restore_item_locked, "bread", list_id)
    assert _item_count(list_id) == MAX_ITEMS_PER_LIST


def test_adding_an_item_works_at_999():
    list_id, _ = default_list()
    _fill_items(list_id, MAX_ITEMS_PER_LIST - 1)
    outcome, _ = write_locked(
        database_crud.add_or_restore_item_locked, "bread", list_id
    )
    assert outcome == "added"
    assert _item_count(list_id) == MAX_ITEMS_PER_LIST


def test_restoring_a_deleted_item_is_refused_when_the_list_is_full():
    list_id, _ = default_list()
    _fill_items(list_id, MAX_ITEMS_PER_LIST)
    with pytest.raises(CountLimitReached):
        write_locked(restore_deleted_item_locked, list_id, "bread", False, [], "", 1)
    assert _item_count(list_id) == MAX_ITEMS_PER_LIST


def test_restoring_a_deleted_item_works_at_999():
    list_id, _ = default_list()
    _fill_items(list_id, MAX_ITEMS_PER_LIST - 1)
    assert (
        write_locked(restore_deleted_item_locked, list_id, "bread", False, [], "", 1)
        is not None
    )
    assert _item_count(list_id) == MAX_ITEMS_PER_LIST


def test_unchecking_an_item_is_allowed_when_the_list_is_full():
    # No new row: the count does not change.
    list_id, _ = default_list()
    _fill_items(list_id, MAX_ITEMS_PER_LIST)
    db.execute(
        "UPDATE items SET done = 1, completed_at = '2026-01-01T00:00:00Z' "
        "WHERE name = 'item 0'"
    )
    db.commit()
    outcome, _ = write_locked(
        database_crud.add_or_restore_item_locked, "item 0", list_id
    )
    assert outcome == "restored"


# Lists per room


def test_creating_a_list_is_refused_when_the_room_is_full():
    room_id, _ = home()
    _fill_lists(room_id, MAX_LISTS_PER_ROOM - 1)  # With the default list: 100.
    assert _list_count(room_id) == MAX_LISTS_PER_ROOM
    with pytest.raises(CountLimitReached, match="at most 100 lists"):
        write_locked(create_or_find_list_locked, "Extra", room_id)
    assert _list_count(room_id) == MAX_LISTS_PER_ROOM


def test_creating_the_100th_list_works():
    room_id, _ = home()
    _fill_lists(room_id, MAX_LISTS_PER_ROOM - 2)  # With the default list: 99.
    _, _, created = write_locked(create_or_find_list_locked, "Extra", room_id)
    assert created is True
    assert _list_count(room_id) == MAX_LISTS_PER_ROOM


def test_finding_an_existing_list_by_name_works_when_the_room_is_full():
    room_id, _ = home()
    _fill_lists(room_id, MAX_LISTS_PER_ROOM - 1)
    _, _, created = write_locked(create_or_find_list_locked, "LIST 5", room_id)
    assert created is False
    assert _list_count(room_id) == MAX_LISTS_PER_ROOM


# Tags per list


def test_adding_a_tag_is_refused_when_the_list_has_50_tags():
    list_id, _ = default_list()
    update_list_tags_settings(list_id, [f"tag {n}" for n in range(MAX_TAGS_PER_LIST)])
    with pytest.raises(CountLimitReached, match="at most 50 tags"):
        write_locked(change_list_tag_locked, list_id, "new tag", add=True)
    row = db.execute("SELECT list_tags FROM lists WHERE id = ?", (list_id,)).fetchone()
    assert "new tag" not in row[0]


def test_an_existing_tag_is_fine_when_the_list_has_50_tags():
    list_id, _ = default_list()
    update_list_tags_settings(list_id, [f"tag {n}" for n in range(MAX_TAGS_PER_LIST)])
    add_list_tag(list_id, "tag 3")  # No error, nothing new.
    row = db.execute("SELECT list_tags FROM lists WHERE id = ?", (list_id,)).fetchone()
    assert row[0].count('"tag 3"') == 1


def test_a_tag_can_be_added_after_one_is_removed():
    list_id, _ = default_list()
    update_list_tags_settings(list_id, [f"tag {n}" for n in range(MAX_TAGS_PER_LIST)])
    write_locked(change_list_tag_locked, list_id, "tag 0", add=False)
    add_list_tag(list_id, "new tag")
    row = db.execute("SELECT list_tags FROM lists WHERE id = ?", (list_id,)).fetchone()
    assert '"new tag"' in row[0]


# Sessions per room


def _token_works(slug: str, token: str) -> bool:
    with _DB_LOCK:
        return _valid_room_id_for_token_locked(slug, token) is not None


def test_sessions_keep_only_the_newest_200_per_room():
    room_id, slug = home()
    tokens = [
        write_locked(_insert_room_access_token_locked, room_id, 1)
        for _ in range(MAX_SESSIONS_PER_ROOM + 1)
    ]
    assert not _token_works(slug, tokens[0])
    assert _token_works(slug, tokens[-1])
    count = db.execute(
        "SELECT COUNT(*) FROM room_access_tokens WHERE room_id = ?", (room_id,)
    ).fetchone()[0]
    assert count == MAX_SESSIONS_PER_ROOM


def test_sign_ins_drop_the_oldest_sessions(monkeypatch):
    # Real bcrypt sign-ins are slow, so the limit is 3 here (read from
    # database_crud, where the sign-in code uses it).
    monkeypatch.setattr(database_crud, "MAX_SESSIONS_PER_ROOM", 3)
    room_id, slug = home()
    tokens = []
    for _ in range(4):
        signed_in = authenticate_room_and_issue_token(slug, "pw")
        assert signed_in is not None
        tokens.append(signed_in[1])
    assert not _token_works(slug, tokens[0])
    assert all(_token_works(slug, token) for token in tokens[1:])
    count = db.execute(
        "SELECT COUNT(*) FROM room_access_tokens WHERE room_id = ?", (room_id,)
    ).fetchone()[0]
    assert count == 3


# Through the ops API: the `too_many` code


def _full_items() -> None:
    _fill_items(default_list()[0], MAX_ITEMS_PER_LIST)


def _full_lists() -> None:
    _fill_lists(home()[0], MAX_LISTS_PER_ROOM - 1)


def _full_tags() -> None:
    update_list_tags_settings(
        default_list()[0], [f"tag {n}" for n in range(MAX_TAGS_PER_LIST)]
    )


OPS_CASES: list[tuple[str, Callable[[], None], Callable[[str], dict[str, Any]]]] = [
    (
        "item.add",
        _full_items,
        lambda list_uid: {"type": "item.add", "list_uid": list_uid, "name": "bread"},
    ),
    (
        "item.restore",
        _full_items,
        lambda list_uid: {
            "type": "item.restore",
            "list_uid": list_uid,
            "name": "bread",
            "done": False,
            "tags": [],
            "description": "",
            "quantity": 1,
            "completed_at": None,
        },
    ),
    (
        "list.create",
        _full_lists,
        lambda list_uid: {"type": "list.create", "name": "Extra"},
    ),
    (
        "list.tag_add",
        _full_tags,
        lambda list_uid: {"type": "list.tag_add", "list_uid": list_uid, "tag": "new"},
    ),
]


@pytest.mark.parametrize(
    ("op_type", "fill", "body"), OPS_CASES, ids=[case[0] for case in OPS_CASES]
)
def test_the_ops_api_refuses_a_full_room_or_list_with_too_many(
    room, op_type, fill, body
):
    _, slug, client = room
    fill()
    _, list_uid = default_list()
    response = op(client, slug, {"op_id": new_id(), **body(list_uid)})
    assert response["status"] == "rejected"
    assert response["code"] == "too_many"
    assert response["message"] in {
        "A list can have at most 1000 items",
        "A room can have at most 100 lists",
        "A list can have at most 50 tags",
    }
