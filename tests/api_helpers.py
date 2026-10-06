"""Shared helpers for the JSON API op tests (not a test module)."""

import uuid
from typing import Any

from fastapi import FastAPI
from starlette.testclient import TestClient

import database_crud as crud
import main
from database_setup import db

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
    crud.add_item_with_state(name, list_id, done, [])
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
