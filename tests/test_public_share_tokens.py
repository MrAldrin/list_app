import sqlite3
from types import SimpleNamespace

import pytest
from api_helpers import (
    create_list,
    get_list_details,
    get_list_details_by_share_token,
    insert_item,
    rename_list,
)

from database_crud import (
    authenticate_room_and_issue_token,
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
    insert_item("Milk", shared.id)


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
