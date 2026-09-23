import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from nicegui import Client, ui
from nicegui.page import page

import main
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
        == "new groceries"
    )
    assert get_list_details_by_share_token(shared.token)["name"] == "new groceries"
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
    assert get_list_details(shared.id)["name"] == "secret groceries"
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
    assert get_list_details(shared.id)["name"] == "secret groceries"


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


@pytest.mark.parametrize("revoke_room", [False, True])
def test_reset_dialog_rechecks_authorization(shared, monkeypatch, revoke_room):
    monkeypatch.setattr(main, "app", SimpleNamespace(storage=SimpleNamespace(user={})))
    monkeypatch.setattr(main, "_cleanup_legacy_room_password_keys", AsyncMock())
    monkeypatch.setattr(
        main, "_get_browser_storage", AsyncMock(return_value=(True, shared.room_token))
    )
    monkeypatch.setattr(main.ui.navigate, "to", Mock())
    monkeypatch.setattr(main, "broadcast_updates", Mock())
    monkeypatch.setattr(main.ui, "notify", Mock())

    async def render():
        with Client(page("/")) as client:
            await main.list_page(shared.slug)
            button = next(
                e
                for e in client.elements.values()
                if isinstance(e, ui.button) and e.text == "Reset share link"
            )
            next(iter(button._event_listeners.values())).handler(None)
            assert get_list_details(shared.id)["share_token"] == shared.token
            if revoke_room:
                update_room_password(shared.room_id, "new-password")
            buttons = [
                e
                for e in client.elements.values()
                if isinstance(e, ui.button) and e.text == "Reset share link"
            ]
            next(iter(buttons[-1]._event_listeners.values())).handler(None)
            assert (get_list_details(shared.id)["share_token"] != shared.token) == (
                not revoke_room
            )
            if revoke_room:
                main.ui.navigate.to.assert_not_called()
            else:
                main.ui.navigate.to.assert_called_once_with(f"/list/{shared.slug}")

    asyncio.run(render())


@pytest.mark.parametrize(
    "public,authorized", [(False, False), (False, True), (True, False), (True, True)]
)
def test_route_access_and_reset_visibility(shared, monkeypatch, public, authorized):
    monkeypatch.setattr(main, "app", SimpleNamespace(storage=SimpleNamespace(user={})))
    monkeypatch.setattr(main, "_cleanup_legacy_room_password_keys", AsyncMock())
    monkeypatch.setattr(
        main,
        "_get_browser_storage",
        AsyncMock(return_value=(True, shared.room_token if authorized else None)),
    )
    monkeypatch.setattr(main.ui.navigate, "to", Mock())

    async def render():
        with Client(page("/")) as client:
            if public:
                await main.shared_list_page(shared.token)
            else:
                await main.list_page(shared.slug)
            labels = [
                e.text for e in client.elements.values() if isinstance(e, ui.label)
            ]
            buttons = [
                e.text for e in client.elements.values() if isinstance(e, ui.button)
            ]
            assert ("secret groceries" in labels) == (public or authorized)
            assert ("Reset share link" in buttons) == authorized
            if not public and not authorized:
                assert "Share" not in buttons
                main.ui.navigate.to.assert_not_called()
            if public:
                field = next(
                    e
                    for e in client.elements.values()
                    if isinstance(e, ui.input) and e.label == "Add or Search"
                )
                field.value = "Blocked after reset"
                rotate_list_share_token(
                    shared.room_slug,
                    shared.room_token,
                    shared.id,
                    expected_slug=shared.slug,
                )
                button = next(
                    e
                    for e in client.elements.values()
                    if isinstance(e, ui.button) and e.text == "Add"
                )
                next(iter(button._event_listeners.values())).handler(None)
                assert db.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0

    asyncio.run(render())
