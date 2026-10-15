"""Shared helpers for the JSON API op tests (not a test module)."""

import json
import uuid
from typing import Any

import bcrypt
from fastapi import FastAPI
from starlette.testclient import TestClient

import main
from database_crud import (
    _DB_LOCK,
    _completion_timestamp,
    _decode_tags,
    _find_list_by_name_locked,
    _list_for_share_token_locked,
    _password_matches,
    _replace_room_password_locked,
    _valid_room_id_for_token_locked,
    change_list_tag_locked,
    change_room_password_locked,
    create_or_find_list_locked,
    delete_room_with_password_locked,
    normalize_item_name,
    rename_room_locked,
    restore_deleted_item_locked,
    rotate_share_token_locked,
    toggle_item_active_tag_locked,
    update_list_visibility_settings_locked,
)
from database_setup import db
from item_visibility import validate_visibility_settings

HTTPS = "https://testserver"


def home() -> tuple[int, str]:
    room_id, slug = db.execute(
        "SELECT id, slug FROM rooms WHERE name = 'Home'"
    ).fetchone()
    return room_id, slug


def client_for(slug: str | None = None, password: str = "pw") -> TestClient:
    client = TestClient(
        main.app,
        base_url=HTTPS,
        headers={"Origin": HTTPS},
        raise_server_exceptions=False,
    )
    if slug is not None:
        response = client.post(
            f"/api/v1/rooms/{slug}/session", json={"password": password}
        )
        assert response.status_code == 200
    return client


def new_id() -> str:
    return str(uuid.uuid4())


def send(client: TestClient, slug: str, body: dict[str, Any]):
    return client.post(f"/api/v1/rooms/{slug}/ops", json=body)


def op(client: TestClient, slug: str, body: dict[str, Any]) -> dict[str, Any]:
    response = send(client, slug, body)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def changes(client: TestClient, slug: str, since: int) -> dict[str, Any]:
    response = client.get(f"/api/v1/rooms/{slug}/changes?since={since}")
    assert response.status_code == 200
    return response.json()


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.headers["cache-control"] == "no-store"


def default_list() -> tuple[int, str]:
    """(id, uid) of the fixture's list."""
    return db.execute("SELECT id, uid FROM lists WHERE name = 'default'").fetchone()


def list_uid_of(list_id: int) -> str:
    return db.execute("SELECT uid FROM lists WHERE id = ?", (list_id,)).fetchone()[0]


def add_item(list_id: int, name: str, *, done: bool = False) -> str:
    """Add an item through the database functions; return its uid."""
    add_item_with_state(name, list_id, done, [])
    return db.execute(
        "SELECT uid FROM items WHERE list_id = ? AND name = ?", (list_id, name)
    ).fetchone()[0]


def item_row(item_uid: str) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT name, done, completed_at, quantity, description, active_tags, "
        "list_id FROM items WHERE uid = ?",
        (item_uid,),
    ).fetchone()
    if row is None:
        return None
    keys = ("name", "done", "completed_at", "quantity", "description", "tags")
    return dict(zip((*keys, "list_id"), row, strict=True))


def processed_ops_count() -> int:
    return db.execute("SELECT COUNT(*) FROM processed_ops").fetchone()[0]


def row_counts() -> tuple[int, int, int]:
    """(lists, items, deletions) in the whole database."""
    return tuple(
        db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("lists", "items", "deletions")
    )


# Direct database setup. These replaced `database_crud` helpers that only tests
# used. Each one calls a live locked helper in one write transaction, or runs
# the same SQL the live code runs.


def write_locked(fn, *args, **kwargs):
    with _DB_LOCK:
        try:
            result = fn(*args, **kwargs)
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise


def create_list(name: str, room_id: int) -> tuple[int, str]:
    list_id, slug, _ = write_locked(create_or_find_list_locked, name, room_id)
    return list_id, slug


def find_list_by_name(name: str, room_id: int) -> tuple[int] | None:
    with _DB_LOCK:
        found = _find_list_by_name_locked(name, room_id)
    return None if found is None else (found[0],)


def rename_list(list_id: int, new_name: str) -> None:
    write_locked(
        db.execute, "UPDATE lists SET name = ? WHERE id = ?", (new_name, list_id)
    )


def update_list_tags_settings(list_id: int, list_tags: list[str]) -> None:
    write_locked(
        db.execute,
        "UPDATE lists SET list_tags = ? WHERE id = ?",
        (json.dumps(list_tags), list_id),
    )


def add_list_tag(list_id: int, tag: str) -> None:
    write_locked(change_list_tag_locked, list_id, tag, add=True)


def remove_list_tag(list_id: int, tag: str) -> None:
    write_locked(change_list_tag_locked, list_id, tag, add=False)


def update_list_visibility_settings(
    list_id: int, *, mode: str, age_days: int, recent_count: int
) -> None:
    validate_visibility_settings(mode, age_days, recent_count)
    write_locked(
        update_list_visibility_settings_locked,
        list_id,
        mode=mode,
        age_days=age_days,
        recent_count=recent_count,
    )


def get_list_details(list_id: int) -> dict | None:
    with _DB_LOCK:
        row = db.execute(
            """
            SELECT l.id, l.name, l.list_tags, l.slug, l.room_id, r.slug, l.share_token,
                   l.hide_done_mode, l.hide_done_age_days, l.hide_done_recent_count
            FROM lists l
            JOIN rooms r ON l.room_id = r.id
            WHERE l.id = ?
            """,
            (list_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "list_tags": _decode_tags(row[2]),
        "slug": row[3],
        "room_id": row[4],
        "room_slug": row[5],
        "share_token": row[6],
        "hide_done_mode": row[7],
        "hide_done_age_days": row[8],
        "hide_done_recent_count": row[9],
    }


def get_list_details_by_slug(slug: str) -> dict | None:
    with _DB_LOCK:
        row = db.execute(
            """
            SELECT l.id, l.name, l.list_tags, l.slug, l.room_id, r.slug,
                   l.hide_done_mode, l.hide_done_age_days, l.hide_done_recent_count
            FROM lists l
            JOIN rooms r ON l.room_id = r.id
            WHERE l.slug = ?
            """,
            (slug,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "list_tags": _decode_tags(row[2]),
        "slug": row[3],
        "room_id": row[4],
        "room_slug": row[5],
        "hide_done_mode": row[6],
        "hide_done_age_days": row[7],
        "hide_done_recent_count": row[8],
    }


def get_list_details_by_share_token(token: str) -> dict | None:
    with _DB_LOCK:
        found = _list_for_share_token_locked(token)
    return get_list_details(found[0]) if found else None


def rotate_list_share_token(list_id: int) -> str:
    return write_locked(rotate_share_token_locked, list_id)


def get_list_data(list_id: int) -> tuple[list[dict], list[str]]:
    with _DB_LOCK:
        rows = db.execute(
            "SELECT id, name, done, active_tags, description, quantity, completed_at "
            "FROM items WHERE list_id = ? "
            "ORDER BY done ASC, name COLLATE NOCASE ASC",
            (list_id,),
        ).fetchall()
    list_items = [
        {
            "id": r[0],
            "name": r[1],
            "done": bool(r[2]),
            "active_tags": _decode_tags(r[3]),
            "description": r[4] or "",
            "quantity": r[5] if r[5] is not None else 1,
            "completed_at": r[6],
        }
        for r in rows
    ]
    list_history_names = sorted({item["name"] for item in list_items})
    return list_items, list_history_names


def find_item_by_name(list_id: int, item_name: str):
    with _DB_LOCK:
        return db.execute(
            "SELECT id, done FROM items WHERE trim(name) = ? COLLATE NOCASE AND list_id = ?",
            (item_name, list_id),
        ).fetchone()


def insert_item(item_name: str, list_id: int) -> None:
    write_locked(
        db.execute,
        "INSERT INTO items (name, done, list_id) VALUES (?, ?, ?)",
        (normalize_item_name(item_name), False, list_id),
    )


def add_item_with_state(
    item_name: str, list_id: int, done: bool, active_tags: list[str], *, now=None
) -> None:
    completed_at = _completion_timestamp(now) if done else None
    write_locked(
        db.execute,
        "INSERT INTO items (name, done, list_id, active_tags, completed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (item_name, done, list_id, json.dumps(active_tags), completed_at),
    )


def restore_item(item_id: int, list_id: int) -> None:
    write_locked(
        db.execute,
        "UPDATE items SET done = 0, completed_at = NULL WHERE id = ? AND list_id = ?",
        (item_id, list_id),
    )


def restore_deleted_item(
    list_id: int,
    name: str,
    done: bool,
    active_tags: list[str],
    description: str,
    quantity: int,
    *,
    completed_at: str | None = None,
) -> bool:
    item_id = write_locked(
        restore_deleted_item_locked,
        list_id,
        name,
        done,
        active_tags,
        description,
        quantity,
        completed_at=completed_at,
    )
    return item_id is not None


def update_item_active_tags(item_id: int, list_id: int, active_tags: list[str]) -> None:
    write_locked(
        db.execute,
        "UPDATE items SET active_tags = ? WHERE id = ? AND list_id = ?",
        (json.dumps(active_tags), item_id, list_id),
    )


def set_item_quantity(item_id: int, list_id: int, quantity: int) -> None:
    write_locked(
        db.execute,
        "UPDATE items SET quantity = ? WHERE id = ? AND list_id = ?",
        (quantity, item_id, list_id),
    )


def toggle_item_active_tag(item_id: int, list_id: int, tag: str) -> bool:
    return write_locked(toggle_item_active_tag_locked, item_id, list_id, tag)


def verify_room(room_slug: str, plain_password: str) -> int | None:
    with _DB_LOCK:
        row = db.execute(
            "SELECT id, password_hash FROM rooms WHERE slug = ?", (room_slug,)
        ).fetchone()
    if not row:
        return None
    room_id, pw_hash = row
    return room_id if _password_matches(plain_password, pw_hash) else None


def validate_room_access_token(room_slug: str, token: str | None) -> int | None:
    with _DB_LOCK:
        return _valid_room_id_for_token_locked(room_slug, token)


def update_room_password(room_id: int, new_plain_password: str) -> bool:
    pw_hash = bcrypt.hashpw(
        new_plain_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    authorization_version = write_locked(
        _replace_room_password_locked, room_id, pw_hash
    )
    return authorization_version is not None


def change_room_password_and_issue_token(
    room_slug: str, current_plain_password: str, new_plain_password: str
) -> tuple[int, str] | None:
    with _DB_LOCK:
        row = db.execute("SELECT id FROM rooms WHERE slug = ?", (room_slug,)).fetchone()
    if not row:
        return None
    token = write_locked(
        change_room_password_locked, row[0], current_plain_password, new_plain_password
    )
    return (row[0], token) if token else None


def delete_room(room_id: int) -> None:
    def delete() -> None:
        for (list_id,) in db.execute(
            "SELECT id FROM lists WHERE room_id = ?", (room_id,)
        ).fetchall():
            db.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
            db.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))

    write_locked(delete)


def delete_room_with_password(room_slug: str, plain_password: str) -> bool:
    with _DB_LOCK:
        row = db.execute("SELECT id FROM rooms WHERE slug = ?", (room_slug,)).fetchone()
    if not row:
        return False
    return write_locked(delete_room_with_password_locked, row[0], plain_password)


def rename_room(room_id: int, new_name: str) -> None:
    write_locked(rename_room_locked, room_id, new_name)


# Admin. Admin sign-in has its own cookie (see `src/admin_access.py`), so admin
# tests serve the API router alone. The `admin_app` fixture is in `conftest.py`.

APP_PASSWORD = "test-only-app-password"  # tests/conftest.py


def browser(admin_app: FastAPI, *, origin: str | None = HTTPS) -> TestClient:
    return TestClient(
        admin_app,
        base_url=HTTPS,
        headers={"Origin": origin} if origin else {},
        raise_server_exceptions=False,
    )


def sign_in(client: TestClient, password: str = APP_PASSWORD):
    return client.post("/api/v1/admin/session", json={"password": password})


def admin(admin_app: FastAPI) -> TestClient:
    client = browser(admin_app)
    assert sign_in(client).status_code == 200
    return client
