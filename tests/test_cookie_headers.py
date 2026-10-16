"""Exact Set-Cookie headers of the room and admin cookies, on HTTPS and plain HTTP.

These pin the flags (HttpOnly, Secure, SameSite, Path, Max-Age) for setting and
clearing each cookie, so a refactor of the cookie helpers cannot change them.
Token and slug values, and the expiry date of cleared cookies, are normalized.
"""

import re

from api_helpers import APP_PASSWORD, HTTPS, browser, home
from starlette.testclient import TestClient

import main
from room_cookies import plain_token_cookie_name, token_cookie_name

HTTP = "http://testserver"
ROOM_MAX_AGE = 31536000  # one year
ADMIN_MAX_AGE = 1209600  # 14 days
ADMIN_HTTPS = "__Host-listapp-admin"
ADMIN_HTTP = "listapp-admin"
LAST_ROOM_HTTPS = "__Host-listapp-last-room"
LAST_ROOM_HTTP = "listapp-last-room"


def normalized(header: str) -> str:
    """The header with its value and any expiry date removed."""
    header = re.sub(r"^([^=]+)=[^;]*", r"\1=<value>", header)
    return re.sub(r"expires=[^;]*; ", "", header)


def headers_of(response) -> list[str]:
    return [normalized(h) for h in response.headers.get_list("set-cookie")]


def set_flags(name: str, max_age: int, secure: bool) -> str:
    flags = f"{name}=<value>; HttpOnly; Max-Age={max_age}; Path=/; SameSite=lax"
    return flags + ("; Secure" if secure else "")


def clear_flags(name: str, secure: bool) -> str:
    return set_flags(name, 0, secure)


def plain_client(app) -> TestClient:
    return TestClient(
        app, base_url=HTTP, headers={"Origin": HTTP}, raise_server_exceptions=False
    )


def https_client(app) -> TestClient:
    return TestClient(
        app, base_url=HTTPS, headers={"Origin": HTTPS}, raise_server_exceptions=False
    )


def admin_sign_in(client: TestClient):
    return client.post("/api/v1/admin/session", json={"password": APP_PASSWORD})


def room_sign_in(client: TestClient, slug: str):
    return client.post(f"/api/v1/rooms/{slug}/session", json={"password": "pw"})


def test_admin_cookie_flags_on_https(admin_app):
    client = browser(admin_app)
    assert headers_of(admin_sign_in(client)) == [
        set_flags(ADMIN_HTTPS, ADMIN_MAX_AGE, secure=True)
    ]
    assert headers_of(client.delete("/api/v1/admin/session")) == [
        clear_flags(ADMIN_HTTPS, secure=True)
    ]
    forged = browser(admin_app)
    forged.cookies.set(ADMIN_HTTPS, "forged", domain="testserver.local")
    assert headers_of(forged.get("/api/v1/admin/session")) == [
        clear_flags(ADMIN_HTTPS, secure=True)
    ]


def test_admin_cookie_flags_on_plain_http(admin_app):
    client = plain_client(admin_app)
    assert headers_of(admin_sign_in(client)) == [
        set_flags(ADMIN_HTTP, ADMIN_MAX_AGE, secure=False)
    ]
    assert headers_of(client.delete("/api/v1/admin/session")) == [
        clear_flags(ADMIN_HTTP, secure=False)
    ]
    forged = plain_client(admin_app)
    forged.cookies.set(ADMIN_HTTP, "forged", domain="testserver.local")
    assert headers_of(forged.get("/api/v1/admin/session")) == [
        clear_flags(ADMIN_HTTP, secure=False)
    ]


def test_room_cookie_flags_on_https_sign_in_and_sign_out():
    _, slug = home()
    client = https_client(main.app)
    token_name = token_cookie_name(slug)
    assert headers_of(room_sign_in(client, slug)) == [
        set_flags(token_name, ROOM_MAX_AGE, secure=True),
        set_flags(LAST_ROOM_HTTPS, ROOM_MAX_AGE, secure=True),
    ]
    assert headers_of(client.delete(f"/api/v1/rooms/{slug}/session")) == [
        clear_flags(token_name, secure=True)
    ]


def test_room_cookie_flags_on_https_when_the_token_is_stale():
    _, slug = home()
    client = https_client(main.app)
    token_name = token_cookie_name(slug)
    client.cookies.set(token_name, "bogus", domain="testserver.local")
    assert headers_of(client.get(f"/api/v1/rooms/{slug}/session")) == [
        clear_flags(token_name, secure=True)
    ]


def test_room_cookie_flags_on_https_password_change():
    _, slug = home()
    client = https_client(main.app)
    room_sign_in(client, slug)
    response = client.post(
        f"/api/v1/rooms/{slug}/password",
        json={"current_password": "pw", "new_password": "pass2"},
    )
    assert headers_of(response) == [
        set_flags(token_cookie_name(slug), ROOM_MAX_AGE, secure=True),
        set_flags(LAST_ROOM_HTTPS, ROOM_MAX_AGE, secure=True),
    ]


def test_room_cookie_flags_on_https_room_delete_clears_both_cookies():
    _, slug = home()
    client = https_client(main.app)
    room_sign_in(client, slug)
    response = client.request(
        "DELETE", f"/api/v1/rooms/{slug}", json={"password": "pw"}
    )
    assert headers_of(response) == [
        clear_flags(token_cookie_name(slug), secure=True),
        clear_flags(LAST_ROOM_HTTPS, secure=True),
    ]


def test_room_cookie_flags_on_plain_http_sign_in_and_sign_out():
    _, slug = home()
    client = plain_client(main.app)
    token_name = plain_token_cookie_name(slug)
    assert headers_of(room_sign_in(client, slug)) == [
        set_flags(token_name, ROOM_MAX_AGE, secure=False),
        set_flags(LAST_ROOM_HTTP, ROOM_MAX_AGE, secure=False),
    ]
    assert headers_of(client.delete(f"/api/v1/rooms/{slug}/session")) == [
        clear_flags(token_name, secure=False)
    ]


def test_room_cookie_flags_on_plain_http_when_the_token_is_stale():
    _, slug = home()
    client = plain_client(main.app)
    token_name = plain_token_cookie_name(slug)
    client.cookies.set(token_name, "bogus", domain="testserver.local")
    assert headers_of(client.get(f"/api/v1/rooms/{slug}/session")) == [
        clear_flags(token_name, secure=False)
    ]
