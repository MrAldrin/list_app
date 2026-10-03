"""SQLite triggers track every write: room change_seq, row changed_seq,
missing uids and deletions. See docs/change-tracking.md."""

import sqlite3
import uuid

import pytest

import database_crud as crud
import item_service
from database_setup import db, init_database


def _home() -> dict:
    return crud.get_rooms()[0]


def _seq(room_id: int) -> int:
    return db.execute(
        "SELECT change_seq FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]


def _row(table: str, row_id: int) -> tuple[str, int]:
    return db.execute(
        f"SELECT uid, changed_seq FROM {table} WHERE id = ?", (row_id,)
    ).fetchone()


def _deletions(room_id: int) -> list[tuple[str, str, int]]:
    return db.execute(
        "SELECT kind, uid, changed_seq FROM deletions WHERE room_id = ? ORDER BY id",
        (room_id,),
    ).fetchall()


def _assert_uuid4(value: str) -> None:
    parsed = uuid.UUID(value)
    assert parsed.version == 4
    assert parsed.variant == uuid.RFC_4122
    assert str(parsed) == value


def _assert_stamped(table: str, row_id: int, room_id: int, before: int) -> None:
    """One write bumps the room seq by exactly 1 and stamps the row with it."""
    seq = _seq(room_id)
    assert seq == before + 1
    assert _row(table, row_id)[1] == seq


@pytest.fixture
def room_id() -> int:
    return _home()["id"]


@pytest.fixture
def shop(room_id) -> tuple[int, str]:
    return crud.create_list("Shop", room_id)


@pytest.fixture
def item_id(shop) -> int:
    item_service.add_or_restore_item(shop[0], "milk", expected_slug=shop[1])
    return crud.find_item_by_name(shop[0], "milk")[0]


# Lists


def test_create_list_fills_uid_and_stamps_seq(room_id):
    before = _seq(room_id)

    list_id, _slug = crud.create_list("Shop", room_id)

    _assert_stamped("lists", list_id, room_id, before)
    _assert_uuid4(_row("lists", list_id)[0])


def test_create_existing_list_changes_nothing(room_id, shop):
    before = _seq(room_id)

    assert crud.create_list("shop", room_id) == shop

    assert _seq(room_id) == before


def test_rename_list_stamps_and_keeps_uid(room_id, shop):
    uid = _row("lists", shop[0])[0]
    before = _seq(room_id)

    status, _ = item_service.rename_list_with_checks(
        shop[0], room_id, "Market", expected_slug=shop[1]
    )

    assert status == item_service.STATUS_RENAMED
    _assert_stamped("lists", shop[0], room_id, before)
    assert _row("lists", shop[0])[0] == uid


def test_rejected_list_rename_changes_nothing(room_id, shop):
    crud.create_list("Market", room_id)
    before = _seq(room_id)

    status, _ = item_service.rename_list_with_checks(
        shop[0], room_id, "market", expected_slug=shop[1]
    )

    assert status == item_service.STATUS_DUPLICATE_NAME
    assert _seq(room_id) == before


@pytest.mark.parametrize(
    "write",
    [
        lambda list_id, slug: crud.add_list_tag(list_id, "Lidl", expected_slug=slug),
        lambda list_id, slug: crud.update_list_tags_settings(
            list_id, ["A", "B"], expected_slug=slug
        ),
        lambda list_id, slug: crud.update_list_visibility_settings(
            list_id, mode="age", age_days=3, recent_count=5, expected_slug=slug
        ),
    ],
    ids=["add_tag", "replace_tags", "visibility"],
)
def test_list_settings_writes_stamp(room_id, shop, write):
    before = _seq(room_id)

    write(*shop)

    _assert_stamped("lists", shop[0], room_id, before)


def test_list_tag_remove_stamps_and_no_op_tag_changes_nothing(room_id, shop):
    crud.add_list_tag(shop[0], "Lidl", expected_slug=shop[1])
    before = _seq(room_id)

    crud.add_list_tag(shop[0], "Lidl", expected_slug=shop[1])
    assert _seq(room_id) == before

    crud.remove_list_tag(shop[0], "Lidl", expected_slug=shop[1])
    _assert_stamped("lists", shop[0], room_id, before)


def test_share_token_rotation_stamps_the_list(room_id, shop):
    # The share token is never sent to clients, but bumping is harmless:
    # the list just shows up unchanged in the next changes feed.
    _, token = crud.authenticate_room_and_issue_token(_home()["slug"], "pw")
    before = _seq(room_id)

    crud.rotate_list_share_token(_home()["slug"], token, shop[0], expected_slug=shop[1])

    _assert_stamped("lists", shop[0], room_id, before)


def test_delete_list_records_list_and_its_items(room_id, shop):
    for name in ("milk", "bread"):
        item_service.add_or_restore_item(shop[0], name, expected_slug=shop[1])
    item_uids = [
        row[0]
        for row in db.execute(
            "SELECT uid FROM items WHERE list_id = ? ORDER BY id", (shop[0],)
        )
    ]
    list_uid = _row("lists", shop[0])[0]
    before = _seq(room_id)

    item_service.delete_list_and_items(shop[0], room_id, expected_slug=shop[1])

    assert _seq(room_id) == before + 3
    deletions = _deletions(room_id)
    assert [(kind, uid) for kind, uid, _ in deletions] == [
        ("item", item_uids[0]),
        ("item", item_uids[1]),
        ("list", list_uid),
    ]
    assert [seq for _, _, seq in deletions] == [before + 1, before + 2, before + 3]


def test_delete_list_with_room_token_records_deletion(room_id, shop):
    _, token = crud.authenticate_room_and_issue_token(_home()["slug"], "pw")
    list_uid = _row("lists", shop[0])[0]

    crud.delete_list_with_room_token(
        _home()["slug"], token, shop[0], expected_slug=shop[1]
    )

    assert _deletions(room_id) == [("list", list_uid, _seq(room_id))]


# Items


def test_add_item_fills_uid_and_stamps(room_id, shop):
    before = _seq(room_id)

    status, _ = item_service.add_or_restore_item(shop[0], "Milk", expected_slug=shop[1])

    assert status == item_service.STATUS_ADDED
    item_id = crud.find_item_by_name(shop[0], "milk")[0]
    _assert_stamped("items", item_id, room_id, before)
    _assert_uuid4(_row("items", item_id)[0])


def test_restore_checked_item_stamps_and_keeps_uid(room_id, shop, item_id):
    item_service.toggle_item_done(shop[0], item_id, True, expected_slug=shop[1])
    uid = _row("items", item_id)[0]
    before = _seq(room_id)

    status, _ = item_service.add_or_restore_item(shop[0], "milk", expected_slug=shop[1])

    assert status == item_service.STATUS_RESTORED
    _assert_stamped("items", item_id, room_id, before)
    assert _row("items", item_id)[0] == uid


def test_duplicate_active_add_changes_nothing(room_id, shop, item_id):
    before = _seq(room_id)

    status, _ = item_service.add_or_restore_item(shop[0], "milk", expected_slug=shop[1])

    assert status == item_service.STATUS_DUPLICATE_ACTIVE
    assert _seq(room_id) == before


@pytest.mark.parametrize(
    "write",
    [
        lambda lid, iid, slug: item_service.toggle_item_done(
            lid, iid, True, expected_slug=slug
        ),
        lambda lid, iid, slug: crud.restore_item(iid, lid, expected_slug=slug),
        lambda lid, iid, slug: item_service.change_item_quantity(
            lid, iid, 1, expected_slug=slug
        ),
        lambda lid, iid, slug: item_service.set_item_quantity(
            lid, iid, 4, expected_slug=slug
        ),
        lambda lid, iid, slug: item_service.update_item_details_with_checks(
            lid, iid, "oat milk", "cold", 2, expected_slug=slug
        ),
        lambda lid, iid, slug: item_service.rename_item_with_checks(
            lid, iid, "oat milk", expected_slug=slug
        ),
        lambda lid, iid, slug: crud.toggle_item_active_tag(
            iid, lid, "Lidl", expected_slug=slug
        ),
        lambda lid, iid, slug: crud.update_item_active_tags(
            iid, lid, ["Lidl"], expected_slug=slug
        ),
    ],
    ids=[
        "toggle_done",
        "restore",
        "quantity_delta",
        "quantity_set",
        "edit",
        "rename",
        "toggle_tag",
        "set_tags",
    ],
)
def test_item_writes_stamp_and_keep_uid(room_id, shop, item_id, write):
    uid = _row("items", item_id)[0]
    before = _seq(room_id)

    write(shop[0], item_id, shop[1])

    _assert_stamped("items", item_id, room_id, before)
    assert _row("items", item_id)[0] == uid


def test_write_to_missing_item_changes_nothing(room_id, shop, item_id):
    before = _seq(room_id)

    item_service.toggle_item_done(shop[0], item_id + 999, True, expected_slug=shop[1])
    crud.toggle_item_active_tag(item_id + 999, shop[0], "Lidl", expected_slug=shop[1])

    assert _seq(room_id) == before


def test_delete_item_records_deletion(room_id, shop, item_id):
    uid = _row("items", item_id)[0]
    before = _seq(room_id)

    item_service.delete_item_from_list(shop[0], item_id, expected_slug=shop[1])

    assert _seq(room_id) == before + 1
    assert _deletions(room_id) == [("item", uid, before + 1)]


def test_undo_delete_creates_item_with_new_uid(room_id, shop, item_id):
    old_uid = _row("items", item_id)[0]
    item_service.delete_item_from_list(shop[0], item_id, expected_slug=shop[1])
    before = _seq(room_id)

    assert crud.restore_deleted_item(
        shop[0], "milk", False, [], "", 1, expected_slug=shop[1]
    )

    new_id = crud.find_item_by_name(shop[0], "milk")[0]
    _assert_stamped("items", new_id, room_id, before)
    new_uid = _row("items", new_id)[0]
    _assert_uuid4(new_uid)
    assert new_uid != old_uid


def test_rejected_undo_changes_nothing(room_id, shop, item_id):
    before = _seq(room_id)

    assert not crud.restore_deleted_item(
        shop[0], "milk", False, [], "", 1, expected_slug=shop[1]
    )

    assert _seq(room_id) == before


@pytest.mark.parametrize(
    "add",
    [
        lambda lid, slug: crud.add_item("eggs", lid, expected_slug=slug),
        lambda lid, slug: crud.add_item_with_state(
            "eggs", lid, True, ["A"], expected_slug=slug
        ),
    ],
    ids=["add_item", "add_item_with_state"],
)
def test_other_item_inserts_stamp(room_id, shop, add):
    before = _seq(room_id)

    add(shop[0], shop[1])

    item_id = crud.find_item_by_name(shop[0], "eggs")[0]
    _assert_stamped("items", item_id, room_id, before)
    _assert_uuid4(_row("items", item_id)[0])


def test_client_uid_is_kept_on_insert(room_id, shop):
    client_uid = str(uuid.uuid4())

    item_id = db.execute(
        "INSERT INTO items (name, done, list_id, uid) VALUES ('eggs', 0, ?, ?)",
        (shop[0], client_uid),
    ).lastrowid
    db.commit()

    assert _row("items", item_id) == (client_uid, _seq(room_id))


def test_sql_uids_are_valid_and_unique(shop):
    for number in range(300):
        db.execute(
            "INSERT INTO items (name, done, list_id) VALUES (?, 0, ?)",
            (f"item {number}", shop[0]),
        )
    db.commit()

    uids = [row[0] for row in db.execute("SELECT uid FROM items")]
    for uid in uids:
        _assert_uuid4(uid)
    assert len(set(uids)) == len(uids)
    # Every variant nibble shows up, so the variant choice is really random.
    assert {uid[19] for uid in uids} == {"8", "9", "a", "b"}


# Rooms


def test_room_rename_bumps_seq(room_id):
    before = _seq(room_id)
    crud.rename_room(room_id, "Family")
    assert _seq(room_id) == before + 1

    _, token = crud.authenticate_room_and_issue_token(_home()["slug"], "pw")
    crud.rename_room_with_room_token(_home()["slug"], token, "Home")
    assert _seq(room_id) == before + 2


def test_password_and_token_changes_do_not_bump(room_id):
    slug = _home()["slug"]
    before = _seq(room_id)

    _, token = crud.authenticate_room_and_issue_token(slug, "pw")
    crud.revoke_room_access_token(slug, token)
    assert crud.change_room_password_and_issue_token(slug, "pw", "new")
    assert crud.update_room_password(room_id, "pw")

    assert _seq(room_id) == before


def _room_with_data(name: str, password_hash: str) -> tuple[int, str]:
    room_id = db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
        (name, f"{name.lower()}-x", password_hash),
    ).lastrowid
    db.commit()
    list_id, slug = crud.create_list("Trip", room_id)
    item_service.add_or_restore_item(list_id, "tent", expected_slug=slug)
    item_service.delete_item_from_list(
        list_id, crud.find_item_by_name(list_id, "tent")[0], expected_slug=slug
    )
    item_service.add_or_restore_item(list_id, "map", expected_slug=slug)
    db.execute(
        "INSERT INTO processed_ops (op_id, room_id, request_hash, response_json) "
        "VALUES (?, ?, 'h', '{}')",
        (str(uuid.uuid4()), room_id),
    )
    db.commit()
    return room_id, f"{name.lower()}-x"


@pytest.mark.parametrize("by_password", [False, True], ids=["admin", "password"])
def test_room_delete_leaves_no_orphans(home_password_hash, room_id, by_password):
    other_id, other_slug = _room_with_data("Other", home_password_hash)
    assert _deletions(other_id)

    if by_password:
        assert crud.delete_room_with_password(other_slug, "pw")
    else:
        crud.delete_room(other_id)

    for table in ("deletions", "processed_ops"):
        assert (
            db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE room_id = ?", (other_id,)
            ).fetchone()[0]
            == 0
        )
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []


# General guarantees


def test_seq_strictly_increases(room_id):
    list_id, slug = crud.create_list("Shop", room_id)
    seqs = [_seq(room_id)]
    item_service.add_or_restore_item(list_id, "milk", expected_slug=slug)
    seqs.append(_seq(room_id))
    item_id = crud.find_item_by_name(list_id, "milk")[0]
    item_service.toggle_item_done(list_id, item_id, True, expected_slug=slug)
    seqs.append(_seq(room_id))
    crud.add_list_tag(list_id, "Lidl", expected_slug=slug)
    seqs.append(_seq(room_id))
    item_service.delete_item_from_list(list_id, item_id, expected_slug=slug)
    seqs.append(_seq(room_id))

    assert seqs == sorted(set(seqs))


def test_other_rooms_are_untouched(home_password_hash, room_id, shop, item_id):
    other_id, _ = _room_with_data("Other", home_password_hash)
    other_seq = _seq(other_id)
    other_rows = db.execute(
        "SELECT l.uid, l.changed_seq, i.uid, i.changed_seq FROM lists AS l "
        "JOIN items AS i ON i.list_id = l.id WHERE l.room_id = ?",
        (other_id,),
    ).fetchall()
    other_deletions = _deletions(other_id)

    item_service.toggle_item_done(shop[0], item_id, True, expected_slug=shop[1])
    crud.rename_room(room_id, "Family")
    item_service.delete_list_and_items(shop[0], room_id, expected_slug=shop[1])

    assert _seq(other_id) == other_seq
    assert (
        db.execute(
            "SELECT l.uid, l.changed_seq, i.uid, i.changed_seq FROM lists AS l "
            "JOIN items AS i ON i.list_id = l.id WHERE l.room_id = ?",
            (other_id,),
        ).fetchall()
        == other_rows
    )
    assert _deletions(other_id) == other_deletions


def test_rolled_back_write_leaves_seq_unchanged(room_id, shop, item_id):
    before = _seq(room_id)
    changed_before = _row("items", item_id)[1]

    db.execute("BEGIN IMMEDIATE")
    db.execute("UPDATE items SET quantity = 5 WHERE id = ?", (item_id,))
    db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    assert _seq(room_id) == before + 2  # the triggers ran inside the transaction
    db.rollback()

    assert _seq(room_id) == before
    assert _row("items", item_id)[1] == changed_before
    assert _deletions(room_id) == []


def test_failed_write_rolls_back_trigger_changes(room_id, shop, item_id):
    before = _seq(room_id)

    with pytest.raises(sqlite3.IntegrityError):
        # Bypasses the duplicate check, so the unique index rejects it; the
        # whole statement and its triggers are undone.
        crud.add_item("milk", shop[0], expected_slug=shop[1])

    assert _seq(room_id) == before


def test_app_connection_keeps_recursive_triggers_off():
    assert db.execute("PRAGMA recursive_triggers").fetchone()[0] == 0


def test_triggers_do_not_loop_even_with_recursive_triggers_on(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "recursive.db"))
    connection = init_database()
    connection.execute("PRAGMA recursive_triggers = ON")
    room = connection.execute("SELECT id FROM rooms").fetchone()[0]

    def seq() -> int:
        return connection.execute(
            "SELECT change_seq FROM rooms WHERE id = ?", (room,)
        ).fetchone()[0]

    list_id = connection.execute(
        "INSERT INTO lists (name, room_id) VALUES ('Shop', ?)", (room,)
    ).lastrowid
    assert seq() == 1
    item = connection.execute(
        "INSERT INTO items (name, done, list_id) VALUES ('milk', 0, ?)", (list_id,)
    ).lastrowid
    assert seq() == 2
    connection.execute("UPDATE items SET done = 1 WHERE id = ?", (item,))
    assert seq() == 3
    connection.execute("UPDATE rooms SET name = 'Family' WHERE id = ?", (room,))
    assert seq() == 4
    assert connection.execute(
        "SELECT changed_seq FROM items WHERE id = ?", (item,)
    ).fetchone() == (3,)
    connection.close()


def test_item_delete_after_its_list_is_gone_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "order.db"))
    connection = init_database()
    room = connection.execute("SELECT id FROM rooms").fetchone()[0]
    list_id = connection.execute(
        "INSERT INTO lists (name, room_id) VALUES ('Shop', ?)", (room,)
    ).lastrowid
    connection.execute(
        "INSERT INTO items (name, done, list_id) VALUES ('milk', 0, ?)", (list_id,)
    )
    connection.commit()
    # Foreign keys normally stop this order; a migration or repair might not.
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("DELETE FROM lists WHERE id = ?", (list_id,))
    seq_after_list = connection.execute("SELECT change_seq FROM rooms").fetchone()[0]

    connection.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
    connection.commit()

    assert connection.execute("SELECT change_seq FROM rooms").fetchone()[0] == (
        seq_after_list
    )
    assert connection.execute("SELECT kind FROM deletions").fetchall() == [("list",)]
    connection.close()
