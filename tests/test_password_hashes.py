"""Password checks fail closed on invalid stored data, without modifying it."""

import sqlite3
from unittest.mock import patch

import pytest

from database_crud import (
    authenticate_room_and_issue_token,
    change_room_password_and_issue_token,
    create_room,
    delete_room_with_password,
    update_room_password,
    verify_room,
)
from database_setup import db


@pytest.mark.parametrize(
    "stored_hash",
    ["", "not-a-hash", "legacy-sha256-hash", "$2b$12$truncated", b"invalid-blob"],
)
@pytest.mark.parametrize("operation", ["verify", "login", "change", "delete"])
def test_invalid_hash_rejects_password_without_changing_data(stored_hash, operation):
    room_id, slug = create_room("Broken hash", "password")
    db.execute(
        "UPDATE rooms SET password_hash = ? WHERE id = ?", (stored_hash, room_id)
    )
    db.commit()
    before = db.execute("SELECT * FROM rooms").fetchall()

    if operation == "verify":
        assert verify_room(slug, "password") is None
    elif operation == "login":
        assert authenticate_room_and_issue_token(slug, "password") is None
    elif operation == "change":
        assert (
            change_room_password_and_issue_token(slug, "password", "new-password")
            is None
        )
    else:
        assert delete_room_with_password(slug, "password") is False

    assert db.execute("SELECT * FROM rooms").fetchall() == before
    assert db.execute("SELECT * FROM room_access_tokens").fetchall() == []
    assert not db.in_transaction

    # An admin reset still repairs the room without needing its broken hash.
    update_room_password(room_id, "reset-password")
    assert verify_room(slug, "reset-password") == room_id


def test_valid_hash_still_accepts_only_correct_password():
    room_id, slug = create_room("Valid hash", "password")
    assert verify_room(slug, "password") == room_id
    assert verify_room(slug, "wrong-password") is None
    assert authenticate_room_and_issue_token(slug, "wrong-password") is None
    assert change_room_password_and_issue_token(slug, "wrong-password", "new") is None
    assert delete_room_with_password(slug, "wrong-password") is False
    assert verify_room(slug, "password") == room_id


def test_database_errors_are_not_swallowed_as_invalid_passwords():
    with patch("database_crud.db") as broken_db:
        broken_db.execute.side_effect = sqlite3.OperationalError("database unavailable")
        with pytest.raises(sqlite3.OperationalError, match="database unavailable"):
            authenticate_room_and_issue_token("room", "password")
