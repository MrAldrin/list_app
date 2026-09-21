import asyncio
import sqlite3
from unittest.mock import AsyncMock

import pytest
from nicegui import Client, core, ui
from nicegui.page import page
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

import main
import room_cookies
from database_crud import authenticate_room_and_issue_token, update_room_password
from database_setup import db
from room_access import RoomAccess, RoomAccessStatus
from room_cookies import LAST_ROOM_COOKIE, token_cookie_name

ORIGIN = "https://testserver"
HEADERS = {"Origin": ORIGIN, "X-Listapp-Request": "1"}


def credentials():
    room = db.execute("SELECT id, slug FROM rooms").fetchone()
    return room[0], room[1], authenticate_room_and_issue_token(room[1], "pw")[1]


def test_secure_cookie_transfer_without_local_storage(monkeypatch):
    room_id, slug, token = credentials()
    browser = TestClient(main.app, base_url=ORIGIN)
    response = browser.post(
        f"/_room-access/{slug}", json={"token": token}, headers=HEADERS
    )
    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    for value in response.headers.get_list("set-cookie"):
        assert "Secure" in value and "HttpOnly" in value
        assert "SameSite=lax" in value and "Path=/" in value
        assert "Domain=" not in value and "Max-Age=31536000" in value
    assert browser.cookies[LAST_ROOM_COOKIE] == slug
    assert (
        browser.post(
            f"/_room-access/{slug}",
            json={"token": token, "check": True},
            headers=HEADERS,
        ).status_code
        == 204
    )
    javascript = AsyncMock(
        side_effect=AssertionError("No localStorage in new installation")
    )
    monkeypatch.setattr(ui, "run_javascript", javascript)
    # Model a new installation receiving cookies but no browser storage.
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "path": "/",
            "headers": [
                (b"host", b"testserver"),
                (
                    b"cookie",
                    f"{token_cookie_name(slug)}={token}; {LAST_ROOM_COOKIE}={slug}".encode(),
                ),
            ],
        }
    )

    async def lookup():
        with Client(page("/"), request=request):
            assert await main._get_browser_storage("listapp_last_room") == (True, slug)
            ok, restored = await main._get_browser_storage(
                main._room_token_storage_key(slug)
            )
            assert ok and restored == token
            access = RoomAccess(room_id, slug, restored, False, lambda: False)
            assert access.check() == RoomAccessStatus.VALID
            update_room_password(room_id, "changed")
            assert access.check() == RoomAccessStatus.INVALID

    asyncio.run(lookup())
    javascript.assert_not_awaited()
    assert (
        browser.post(
            f"/_room-access/{slug}", json={"token": token}, headers=HEADERS
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": ORIGIN},
        {"X-Listapp-Request": "1"},
        {**HEADERS, "Origin": "https://evil.example"},
        {**HEADERS, "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cookie_writes_reject_forged_requests(headers):
    _, slug, token = credentials()
    response = TestClient(main.app, base_url=ORIGIN).post(
        f"/_room-access/{slug}", json={"token": token}, headers=headers
    )
    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_http_invalid_tokens_and_missing_rooms_cannot_set_cookies():
    _, slug, token = credentials()
    client = TestClient(main.app, base_url=ORIGIN)
    for path, body, status in [
        (slug, {"token": "bad"}, 401),
        ("missing", {"token": token}, 401),
        (slug, {"token": None}, 400),
        (slug, [], 400),
        (slug, {"token": token, "check": True}, 401),
    ]:
        response = client.post(f"/_room-access/{path}", json=body, headers=HEADERS)
        assert response.status_code == status
        assert "set-cookie" not in response.headers
    assert (
        TestClient(main.app)
        .post(f"/_room-access/{slug}", json={"token": token}, headers=HEADERS)
        .status_code
        == 403
    )


def test_cookie_tokens_remain_room_scoped_and_deleted_rooms_fail_closed():
    _, slug, token = credentials()
    db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
        ("Other", "other-room", "unused"),
    )
    db.commit()
    client = TestClient(main.app, base_url=ORIGIN)
    assert (
        client.post(
            "/_room-access/other-room", json={"token": token}, headers=HEADERS
        ).status_code
        == 401
    )
    db.execute("DELETE FROM lists")
    db.execute("DELETE FROM rooms WHERE slug = ?", (slug,))
    db.commit()
    assert (
        client.post(
            f"/_room-access/{slug}", json={"token": token}, headers=HEADERS
        ).status_code
        == 401
    )


@pytest.mark.parametrize("path", ["/", "/room/example", "/list/example"])
def test_personalized_pages_are_not_cached(path):
    request = Request({"type": "http", "path": path, "headers": []})
    response = asyncio.run(
        main.auth_middleware(request, AsyncMock(return_value=Response()))
    )
    assert response.headers["cache-control"] == "no-store"


def test_cookie_cleanup_and_database_failure(monkeypatch):
    _, slug, token = credentials()
    client = TestClient(main.app, base_url=ORIGIN)
    client.post(f"/_room-access/{slug}", json={"token": token}, headers=HEADERS)

    def unavailable(*args):
        raise sqlite3.OperationalError("offline")

    monkeypatch.setattr(room_cookies, "validate_room_access_token", unavailable)
    response = client.post(
        f"/_room-access/{slug}", json={"token": token}, headers=HEADERS
    )
    assert response.status_code == 503 and "set-cookie" not in response.headers
    assert token_cookie_name(slug) in client.cookies
    assert (
        client.post(
            f"/_room-access/{slug}", json={"clear": True}, headers=HEADERS
        ).status_code
        == 204
    )
    assert token_cookie_name(slug) not in client.cookies


def test_legacy_token_migration_and_storage_fallback(monkeypatch):
    _, slug, token = credentials()
    store = AsyncMock(return_value=True)
    monkeypatch.setattr(main, "_store_room_cookie", store)
    javascript = AsyncMock(return_value=token)
    monkeypatch.setattr(ui, "run_javascript", javascript)

    async def migrate():
        request = Request(
            {
                "type": "http",
                "scheme": "http",
                "path": "/",
                "headers": [(b"host", b"testserver")],
            }
        )
        with Client(page("/"), request=request):
            assert await main._get_browser_storage(
                main._room_token_storage_key(slug)
            ) == (True, token)
            store.assert_awaited_once_with(slug, token)
            javascript.reset_mock()
            assert await main._store_room_access(slug, token)
            javascript.assert_not_awaited()
            store.return_value = False
            assert await main._store_room_access(slug, token)
            assert "localStorage.setItem" in javascript.call_args.args[0]

    asyncio.run(migrate())


@pytest.mark.parametrize("scheme", ["https", "wss"])
def test_socket_transport_rejects_cross_origin(scheme):
    assert core.sio.eio.cors_allowed_origins is room_cookies.same_origin_socket
    environ = {
        "wsgi.url_scheme": "http",
        "asgi.scope": {"scheme": scheme},
        "HTTP_HOST": "testserver",
        "HTTP_ORIGIN": "https://evil.example",
        "HTTP_X_FORWARDED_HOST": "evil.example",
    }
    assert "https://evil.example" not in core.sio.eio._cors_allowed_origins(environ)
    environ["HTTP_ORIGIN"] = ORIGIN
    assert ORIGIN in core.sio.eio._cors_allowed_origins(environ)
