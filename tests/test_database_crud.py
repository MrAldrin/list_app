import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from api_helpers import (
    change_room_password_and_issue_token,
    create_list,
    delete_room,
    delete_room_with_password,
    find_item_by_name,
    get_list_data,
    get_list_details_by_slug,
    insert_item,
    rename_room,
    validate_room_access_token,
    verify_room,
)

from database_crud import (
    ListUnavailable,
    add_or_restore_item_atomic,
    authenticate_room_and_issue_token,
    create_room,
    delete_item,
    delete_list,
    get_lists,
    normalize_item_name,
    reset_room_password_by_slug,
    revoke_room_access_token,
    update_item_details,
    update_item_done,
    update_item_quantity,
)
from database_setup import db


@pytest.fixture
def room_id():
    room_id_value, _ = create_room("Test Room", "pw")
    return room_id_value


def test_normalize_item_name():
    # Verify that raw item names are correctly stripped, lowercased, and handle None.
    assert normalize_item_name(raw="  Apples  ") == "apples"
    assert normalize_item_name(raw=None) == ""
    assert normalize_item_name(raw="\nBREAD\t") == "bread"


def test_create_list_success(room_id):
    # Verify that a new list can be created and is included in the list of all lists.
    list_id, _ = create_list(name="Groceries", room_id=room_id)
    assert list_id is not None
    lists = get_lists(room_id)
    assert len(lists) == 1
    assert any(entry[1] == "Groceries" for entry in lists)


def test_create_list_duplicate(room_id):
    # Verify that creating a list with a name that already exists returns the existing ID.
    create_list(name="Groceries", room_id=room_id)
    # This should return the same ID and keep the first spelling
    create_list(name="GROCERIES", room_id=room_id)
    lists = get_lists(room_id)
    assert [entry[1] for entry in lists] == ["Groceries"]


def test_create_list_empty(room_id):
    # Verify that creating a list with an empty or whitespace-only name raises a ValueError.
    with pytest.raises(
        expected_exception=ValueError, match="List name cannot be empty"
    ):
        create_list(name="", room_id=room_id)
    with pytest.raises(
        expected_exception=ValueError, match="List name cannot be empty"
    ):
        create_list(name="   ", room_id=room_id)


def test_failed_create_list_rolls_back_and_connection_recovers(room_id):
    before = db.execute(
        "SELECT id, name, list_tags, slug, room_id, share_token FROM lists ORDER BY id"
    ).fetchall()
    db.execute(
        "CREATE TEMP TRIGGER fail_create_list BEFORE INSERT ON lists "
        "WHEN NEW.name = 'Blocked' "
        "BEGIN SELECT RAISE(ABORT, 'injected list creation failure'); END"
    )
    try:
        with pytest.raises(
            sqlite3.IntegrityError, match="injected list creation failure"
        ):
            create_list("Blocked", room_id)

        assert (
            db.execute(
                "SELECT id, name, list_tags, slug, room_id, share_token "
                "FROM lists ORDER BY id"
            ).fetchall()
            == before
        )
        assert not db.in_transaction

        list_id, _ = create_list("Recovered", room_id)
        assert db.execute(
            "SELECT name FROM lists WHERE id = ?", (list_id,)
        ).fetchone() == ("Recovered",)
    finally:
        db.rollback()
        db.execute("DROP TRIGGER IF EXISTS fail_create_list")
        db.commit()


def test_update_item_done(room_id):
    # Verify that an item's completion status can be updated.
    list_id, _ = create_list(name="My List", room_id=room_id)
    insert_item(item_name="Apples", list_id=list_id)
    item_id, _ = find_item_by_name(list_id=list_id, item_name="apples")

    update_item_done(item_id=item_id, list_id=list_id, done=True)
    item = find_item_by_name(list_id=list_id, item_name="apples")
    assert item[1] == 1  # done=True

    update_item_done(item_id=item_id, list_id=list_id, done=False)
    item = find_item_by_name(list_id=list_id, item_name="apples")
    assert item[1] == 0  # done=False


def test_get_lists_sorting(room_id):
    # Verify that lists are returned sorted by name (case-insensitive).
    create_list(name="Zebra", room_id=room_id)
    create_list(name="Apple", room_id=room_id)
    create_list(name="banana", room_id=room_id)

    lists = get_lists(room_id)
    names = [entry[1] for entry in lists if entry[1] != "default"]
    assert names == ["Apple", "banana", "Zebra"]


def test_delete_item(room_id):
    # Verify that an item can be removed from a list.
    list_id, _ = create_list(name="My List", room_id=room_id)
    insert_item(item_name="Apples", list_id=list_id)
    apple_id, _ = find_item_by_name(list_id=list_id, item_name="apples")

    delete_item(item_id=apple_id, list_id=list_id)
    assert find_item_by_name(list_id=list_id, item_name="apples") is None


def test_delete_nonexistent_item(room_id):
    # Verify that attempting to delete an item that doesn't exist does not raise an error.
    list_id, _ = create_list(name="My List", room_id=room_id)
    # This should simply do nothing and not crash
    delete_item(item_id=999, list_id=list_id)


def test_update_nonexistent_item_done(room_id):
    # Verify that attempting to update a non-existent item does not raise an error.
    list_id, _ = create_list(name="My List", room_id=room_id)
    update_item_done(item_id=999, list_id=list_id, done=True)


def test_delete_list(room_id):
    # Verify that a list and its items are correctly deleted.
    list_id, _ = create_list(name="Delete Me", room_id=room_id)
    insert_item(item_name="Item 1", list_id=list_id)

    delete_list(list_id=list_id)

    lists = get_lists(room_id)
    assert not any(entry[0] == list_id for entry in lists)

    # Verify items are gone too
    items, _ = get_list_data(list_id=list_id)
    assert len(items) == 0


def test_failed_list_delete_restores_items(room_id):
    list_id, slug = create_list("Keep list", room_id)
    insert_item("Keep item", list_id)
    db.execute(
        "CREATE TEMP TRIGGER fail_list_delete BEFORE DELETE ON lists "
        "BEGIN SELECT RAISE(ABORT, 'injected delete failure'); END"
    )
    try:
        with pytest.raises(Exception, match="injected delete failure"):
            delete_list(list_id)
        assert not db.in_transaction
        assert get_list_details_by_slug(slug) is not None
        assert len(get_list_data(list_id)[0]) == 1
    finally:
        db.execute("DROP TRIGGER fail_list_delete")


def test_mutations_fail_without_creating_data_for_deleted_list(room_id):
    list_id, _ = create_list(name="Delete Me", room_id=room_id)
    delete_list(list_id)

    with pytest.raises(ListUnavailable):
        add_or_restore_item_atomic("orphan", list_id)
    with pytest.raises(ListUnavailable):
        update_item_done(item_id=1, list_id=list_id, done=True)
    with pytest.raises(ListUnavailable):
        update_item_quantity(list_id=list_id, item_id=1, quantity=2)

    assert get_list_data(list_id) == ([], [])


def test_concurrent_db_operations_do_not_share_cursor_state(room_id):
    # Regression test: concurrent CRUD calls should not fail with shared-cursor errors.
    worker_count = 6
    operations_per_worker = 20

    def worker(worker_id: int):
        local_errors = []
        for i in range(operations_per_worker):
            try:
                list_id, _ = create_list(
                    name=f"worker-{worker_id}-list-{i}", room_id=room_id
                )
                insert_item(item_name=f"item-{worker_id}-{i}", list_id=list_id)
                get_list_data(list_id=list_id)
                get_lists(room_id)
            except Exception as exc:  # noqa: BLE001 - capture worker failures for assertion context
                local_errors.append(exc)
        return local_errors

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(executor.map(worker, range(worker_count)))

    errors = [error for worker_errors in results for error in worker_errors]
    assert errors == []


def test_failed_create_room_rolls_back_and_connection_recovers():
    before = db.execute("SELECT * FROM rooms ORDER BY id").fetchall()
    db.execute(
        "CREATE TEMP TRIGGER fail_create_room BEFORE INSERT ON rooms "
        "WHEN NEW.name = 'Blocked room' "
        "BEGIN SELECT RAISE(ABORT, 'injected room creation failure'); END"
    )
    try:
        with pytest.raises(
            sqlite3.IntegrityError, match="injected room creation failure"
        ):
            create_room("Blocked room", "password")

        assert db.execute("SELECT * FROM rooms ORDER BY id").fetchall() == before
        assert not db.in_transaction

        room_id, slug = create_room("Recovered room", "password")
        assert db.execute(
            "SELECT name, slug FROM rooms WHERE id = ?", (room_id,)
        ).fetchone() == ("Recovered room", slug)
    finally:
        db.rollback()
        db.execute("DROP TRIGGER IF EXISTS fail_create_room")
        db.commit()


def test_room_access_tokens_are_hashed_and_bound_to_one_room():
    first_room_id, first_slug = create_room("First room", "first-password")
    _, second_slug = create_room("Second room", "second-password")

    authenticated = authenticate_room_and_issue_token(first_slug, "first-password")

    assert authenticated is not None
    room_id, token = authenticated
    assert room_id == first_room_id
    assert validate_room_access_token(first_slug, token) == first_room_id
    assert validate_room_access_token(second_slug, token) is None
    stored_hash = db.execute(
        "SELECT token_hash FROM room_access_tokens WHERE room_id = ?", (first_room_id,)
    ).fetchone()[0]
    assert stored_hash != token
    assert len(stored_hash) == 64


def test_password_reset_revokes_every_existing_room_token():
    room_id_value, room_slug = create_room("Token room", "old-password")
    first_token = authenticate_room_and_issue_token(room_slug, "old-password")[1]
    second_token = authenticate_room_and_issue_token(room_slug, "old-password")[1]
    version_before = db.execute(
        "SELECT authorization_version FROM rooms WHERE id = ?", (room_id_value,)
    ).fetchone()[0]

    reset_room_password_by_slug(room_slug, "new-password")

    assert validate_room_access_token(room_slug, first_token) is None
    assert validate_room_access_token(room_slug, second_token) is None
    assert (
        db.execute(
            "SELECT COUNT(*) FROM room_access_tokens WHERE room_id = ?",
            (room_id_value,),
        ).fetchone()[0]
        == 0
    )
    assert (
        db.execute(
            "SELECT authorization_version FROM rooms WHERE id = ?", (room_id_value,)
        ).fetchone()[0]
        == version_before + 1
    )


def test_failed_password_reset_token_deletion_rolls_back_and_recovers():
    room_id_value, room_slug = create_room("Token room", "old-password")
    first_token = authenticate_room_and_issue_token(room_slug, "old-password")[1]
    second_token = authenticate_room_and_issue_token(room_slug, "old-password")[1]
    before = db.execute(
        "SELECT password_hash, authorization_version FROM rooms WHERE id = ?",
        (room_id_value,),
    ).fetchone()
    tokens_before = db.execute(
        "SELECT * FROM room_access_tokens WHERE room_id = ?", (room_id_value,)
    ).fetchall()
    db.execute(
        "CREATE TEMP TRIGGER fail_password_reset_token_deletion "
        "BEFORE DELETE ON room_access_tokens "
        f"WHEN OLD.room_id = {room_id_value} "
        "BEGIN SELECT RAISE(ABORT, 'injected password reset failure'); END"
    )
    try:
        with pytest.raises(
            sqlite3.IntegrityError, match="injected password reset failure"
        ):
            reset_room_password_by_slug(room_slug, "new-password")

        assert (
            db.execute(
                "SELECT password_hash, authorization_version FROM rooms WHERE id = ?",
                (room_id_value,),
            ).fetchone()
            == before
        )
        assert (
            db.execute(
                "SELECT * FROM room_access_tokens WHERE room_id = ?", (room_id_value,)
            ).fetchall()
            == tokens_before
        )
        assert verify_room(room_slug, "old-password") == room_id_value
        assert validate_room_access_token(room_slug, first_token) == room_id_value
        assert validate_room_access_token(room_slug, second_token) == room_id_value
        assert not db.in_transaction

        db.execute("DROP TRIGGER fail_password_reset_token_deletion")
        assert reset_room_password_by_slug(room_slug, "recovered-password")
        assert verify_room(room_slug, "recovered-password") == room_id_value
        assert validate_room_access_token(room_slug, first_token) is None
        assert validate_room_access_token(room_slug, second_token) is None
    finally:
        db.rollback()
        db.execute("DROP TRIGGER IF EXISTS fail_password_reset_token_deletion")
        db.commit()


def test_normal_password_change_issues_only_a_fresh_token_to_changing_device():
    room_id_value, room_slug = create_room("Token room", "old-password")
    old_token = authenticate_room_and_issue_token(room_slug, "old-password")[1]

    changed = change_room_password_and_issue_token(
        room_slug, "old-password", "new-password"
    )

    assert changed is not None
    changed_room_id, new_token = changed
    assert changed_room_id == room_id_value
    assert validate_room_access_token(room_slug, old_token) is None
    assert validate_room_access_token(room_slug, new_token) == room_id_value
    assert authenticate_room_and_issue_token(room_slug, "old-password") is None


def test_failed_room_rename_rolls_back_and_connection_recovers(room_id):
    before = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    db.execute(
        "CREATE TEMP TRIGGER fail_room_rename BEFORE UPDATE OF name ON rooms "
        f"WHEN OLD.id = {room_id} AND NEW.name = 'Blocked name' "
        "BEGIN SELECT RAISE(ABORT, 'injected room rename failure'); END"
    )
    try:
        with pytest.raises(
            sqlite3.IntegrityError, match="injected room rename failure"
        ):
            rename_room(room_id, "Blocked name")

        assert (
            db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
            == before
        )
        assert not db.in_transaction

        rename_room(room_id, "Recovered name")
        assert db.execute(
            "SELECT name FROM rooms WHERE id = ?", (room_id,)
        ).fetchone() == ("Recovered name",)
    finally:
        db.rollback()
        db.execute("DROP TRIGGER IF EXISTS fail_room_rename")
        db.commit()


def test_failed_token_revocation_keeps_access_and_connection_recovers(room_id):
    room_slug = db.execute(
        "SELECT slug FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]
    token = authenticate_room_and_issue_token(room_slug, "pw")[1]
    before = db.execute(
        "SELECT * FROM room_access_tokens WHERE room_id = ?", (room_id,)
    ).fetchall()
    db.execute(
        "CREATE TEMP TRIGGER fail_room_token_revocation "
        "BEFORE UPDATE OF revoked_at ON room_access_tokens "
        f"WHEN OLD.room_id = {room_id} "
        "BEGIN SELECT RAISE(ABORT, 'injected token revocation failure'); END"
    )
    try:
        with pytest.raises(
            sqlite3.IntegrityError, match="injected token revocation failure"
        ):
            revoke_room_access_token(room_slug, token)

        assert (
            db.execute(
                "SELECT * FROM room_access_tokens WHERE room_id = ?", (room_id,)
            ).fetchall()
            == before
        )
        assert validate_room_access_token(room_slug, token) == room_id
        assert not db.in_transaction

        rename_room(room_id, "Still writable")
        assert db.execute(
            "SELECT name FROM rooms WHERE id = ?", (room_id,)
        ).fetchone() == ("Still writable",)

        db.execute("DROP TRIGGER fail_room_token_revocation")
        revoke_room_access_token(room_slug, token)
        assert validate_room_access_token(room_slug, token) is None
    finally:
        db.rollback()
        db.execute("DROP TRIGGER IF EXISTS fail_room_token_revocation")
        db.commit()


def test_deleting_a_room_cascades_to_its_access_tokens():
    _, room_slug = create_room("Token room", "password")
    authenticate_room_and_issue_token(room_slug, "password")

    delete_room_with_password(room_slug, "password")

    assert db.execute("SELECT COUNT(*) FROM room_access_tokens").fetchone()[0] == 0


@pytest.mark.parametrize("authorized", [False, True])
def test_failed_room_delete_restores_all_rows(authorized):
    room_id, slug = create_room("Keep room", "password")
    list_id, _ = create_list("Keep list", room_id)
    insert_item("Keep item", list_id)
    token = authenticate_room_and_issue_token(slug, "password")[1]
    db.execute(
        "CREATE TEMP TRIGGER fail_room_delete BEFORE DELETE ON rooms "
        "BEGIN SELECT RAISE(ABORT, 'injected delete failure'); END"
    )
    try:
        with pytest.raises(Exception, match="injected delete failure"):
            if authorized:
                delete_room_with_password(slug, "password")
            else:
                delete_room(room_id)
        assert not db.in_transaction
        assert db.execute("SELECT 1 FROM rooms WHERE id = ?", (room_id,)).fetchone()
        assert get_lists(room_id)[0][0] == list_id
        assert len(get_list_data(list_id)[0]) == 1
        assert validate_room_access_token(slug, token) == room_id
    finally:
        db.execute("DROP TRIGGER fail_room_delete")


def test_login_token_cannot_remain_valid_when_a_password_reset_races_it():
    _, room_slug = create_room("Token room", "old-password")
    password_check_started = threading.Event()
    finish_password_check = threading.Event()

    import bcrypt

    original_checkpw = bcrypt.checkpw

    def delayed_checkpw(*args):
        password_check_started.set()
        assert finish_password_check.wait(timeout=5)
        return original_checkpw(*args)

    with (
        patch("database_crud.bcrypt.checkpw", side_effect=delayed_checkpw),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        login = executor.submit(
            authenticate_room_and_issue_token, room_slug, "old-password"
        )
        assert password_check_started.wait(timeout=5)
        reset = executor.submit(reset_room_password_by_slug, room_slug, "new-password")
        finish_password_check.set()
        authenticated = login.result(timeout=10)
        reset.result(timeout=10)

    assert authenticated is not None
    assert validate_room_access_token(room_slug, authenticated[1]) is None


def test_update_item_details(room_id):
    # Verify updating name and description for an item.
    list_id, _ = create_list(name="My List", room_id=room_id)
    insert_item(item_name="Apples", list_id=list_id)

    items, _ = get_list_data(list_id=list_id)
    item_id = items[0]["id"]
    assert items[0]["description"] == ""

    update_item_details(
        item_id=item_id,
        list_id=list_id,
        name="fuji apples",
        description="Buy 3 large ones",
    )
    updated_items, _ = get_list_data(list_id=list_id)
    assert updated_items[0]["name"] == "fuji apples"
    assert updated_items[0]["description"] == "Buy 3 large ones"
