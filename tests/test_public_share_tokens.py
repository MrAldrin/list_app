import sqlite3
from types import SimpleNamespace

import pytest

from database_crud import (
    ListUnavailable,
    add_item,
    authenticate_room_and_issue_token,
    create_list,
    create_room,
    get_list_details,
    get_list_details_by_share_token,
    rename_list,
    rename_list_with_room_token,
    rotate_list_share_token,
    update_room_password,
)
from database_setup import db, init_database


@pytest.fixture
def shared():
    room_id, room_slug = db.execute("SELECT id, slug FROM rooms").fetchone()
    _, room_token = authenticate_room_and_issue_token(room_slug, "pw")
    list_id, slug = create_list("Secret groceries", room_id)
    return SimpleNamespace(
        room_id=room_id,
        room_slug=room_slug,
        room_token=room_token,
        id=list_id,
        slug=slug,
        token=get_list_details(list_id)["share_token"],
    )


def test_tokens_unique_stable_and_scoped(shared):
    other, _ = create_list("Other", shared.room_id)
    assert len(shared.token) == 43
    assert get_list_details(other)["share_token"] != shared.token
    assert get_list_details_by_share_token(shared.token)["id"] == shared.id
    for invalid in ("", shared.token[:-1], "x" * 43, shared.slug):
        assert get_list_details_by_share_token(invalid) is None
    rename_list(shared.id, "Renamed")
    assert get_list_details_by_share_token(shared.token)["name"] == "Renamed"
    add_item("Milk", shared.id, expected_slug=f"share:{shared.token}")


@pytest.mark.parametrize("credential", ["missing", "public", "wrong-room", "revoked"])
def test_rotation_requires_current_authorization_for_own_room(shared, credential):
    token, room_slug = "", shared.room_slug
    if credential == "public":
        token = shared.token
    elif credential == "wrong-room":
        _, room_slug = create_room("Other", "other-pw")
        _, token = authenticate_room_and_issue_token(room_slug, "other-pw")
    elif credential == "revoked":
        token = shared.room_token
        update_room_password(shared.room_id, "new-pw")
    with pytest.raises(PermissionError):
        rotate_list_share_token(room_slug, token, shared.id, expected_slug=shared.slug)
    assert get_list_details_by_share_token(shared.token)


def test_room_token_can_rename_without_rotating_public_link(shared):
    assert (
        rename_list_with_room_token(
            shared.room_slug,
            shared.room_token,
            shared.id,
            "New groceries",
            expected_slug=shared.slug,
        )
        == "New groceries"
    )
    assert get_list_details_by_share_token(shared.token)["name"] == "New groceries"
    assert get_list_details(shared.id)["share_token"] == shared.token


@pytest.mark.parametrize("credential", ["missing", "public", "wrong-room", "revoked"])
def test_room_rename_rejects_non_room_grants(shared, credential):
    token, room_slug = "", shared.room_slug
    if credential == "public":
        token = shared.token
    elif credential == "wrong-room":
        _, room_slug = create_room("Other", "other-pw")
        _, token = authenticate_room_and_issue_token(room_slug, "other-pw")
    elif credential == "revoked":
        token = shared.room_token
        update_room_password(shared.room_id, "new-pw")
    with pytest.raises(PermissionError):
        rename_list_with_room_token(
            room_slug, token, shared.id, "Forbidden", expected_slug=shared.slug
        )
    assert get_list_details(shared.id)["name"] == "Secret groceries"
    assert get_list_details(shared.id)["share_token"] == shared.token


def test_room_rename_rejects_invalid_name(shared):
    with pytest.raises(ValueError, match="cannot be empty"):
        rename_list_with_room_token(
            shared.room_slug,
            shared.room_token,
            shared.id,
            "   ",
            expected_slug=shared.slug,
        )
    assert get_list_details(shared.id)["name"] == "Secret groceries"


def test_rotation_blocks_already_open_public_writes(shared):
    new = rotate_list_share_token(
        shared.room_slug, shared.room_token, shared.id, expected_slug=shared.slug
    )
    assert new != shared.token
    assert get_list_details_by_share_token(shared.token) is None
    with pytest.raises(ListUnavailable):
        add_item("Forbidden", shared.id, expected_slug=f"share:{shared.token}")
    add_item("Allowed", shared.id, expected_slug=f"share:{new}")
    add_item("Room edit", shared.id, expected_slug=shared.slug)
    assert db.execute("SELECT name FROM items ORDER BY id").fetchall() == [
        ("Allowed",),
        ("Room edit",),
    ]


def test_legacy_migration_backfills_without_changing_data_and_survives_restart(
    tmp_path, monkeypatch
):
    path = tmp_path / "legacy.db"
    monkeypatch.setenv("DB_PATH", str(path))
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE lists (id INTEGER PRIMARY KEY, name TEXT UNIQUE, list_tags TEXT DEFAULT '[]')"
    )
    conn.execute("INSERT INTO lists (id, name) VALUES (7, 'Old list')")
    conn.commit()
    conn.close()
    conn = init_database()
    before = conn.execute(
        "SELECT id, name, slug, room_id, share_token FROM lists"
    ).fetchone()
    assert before[:2] == (7, "Old list")
    assert len(before[4]) == 43
    conn.close()
    conn = init_database()
    assert (
        conn.execute(
            "SELECT id, name, slug, room_id, share_token FROM lists"
        ).fetchone()
        == before
    )
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()
