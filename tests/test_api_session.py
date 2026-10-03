"""Room session endpoints of the JSON API (docs/api.md, "Room session")."""

import sqlite3
from http.cookies import SimpleCookie

import pytest
from starlette.testclient import TestClient

import database_crud
import main
from database_crud import (
    authenticate_room_and_issue_token,
    change_room_password_and_issue_token,
    create_room,
    update_room_password,
    validate_room_access_token,
)
from database_setup import db
from room_cookies import (
    LAST_ROOM_COOKIE,
    PLAIN_LAST_ROOM_COOKIE,
    plain_token_cookie_name,
    token_cookie_name,
)

HTTPS = "https://testserver"
HTTP = "http://testserver"


def room() -> tuple[int, str]:
    room_id, slug = db.execute("SELECT id, slug FROM rooms").fetchone()
    return room_id, slug


def browser(origin: str = HTTPS) -> TestClient:
    return TestClient(
        main.app,
        base_url=origin,
        headers={"Origin": origin},
        raise_server_exceptions=False,
    )


def sign_in(client: TestClient, slug: str, password: str = "pw"):
    return client.post(f"/api/v1/rooms/{slug}/session", json={"password": password})


def set_cookies(response) -> dict[str, SimpleCookie]:
    cookies = {}
    for header in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        cookie.load(header)
        name = next(iter(cookie))
        cookies[name] = cookie[name]
    return cookies


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.headers["cache-control"] == "no-store"


def test_sign_in_sets_the_https_cookies():
    _, slug = room()
    client = browser()
    response = sign_in(client, slug)
    assert response.status_code == 200
    assert response.json() == {"room": {"slug": slug, "name": "Home"}}
    assert response.headers["cache-control"] == "no-store"
    cookies = set_cookies(response)
    assert set(cookies) == {token_cookie_name(slug), LAST_ROOM_COOKIE}
    for cookie in cookies.values():
        assert cookie["secure"] is True
        assert cookie["httponly"] is True
        assert cookie["samesite"].lower() == "lax"
        assert cookie["path"] == "/"
        assert cookie["max-age"] == str(60 * 60 * 24 * 365)
        assert not cookie["domain"]
    assert cookies[LAST_ROOM_COOKIE].value == slug
    token = cookies[token_cookie_name(slug)].value
    assert validate_room_access_token(slug, token) is not None
    assert token not in response.text


def test_sign_in_on_plain_http_uses_plain_cookies_without_secure():
    _, slug = room()
    client = browser(HTTP)
    response = sign_in(client, slug)
    assert response.status_code == 200
    cookies = set_cookies(response)
    assert set(cookies) == {plain_token_cookie_name(slug), PLAIN_LAST_ROOM_COOKIE}
    for cookie in cookies.values():
        assert not cookie["secure"]
        assert cookie["httponly"] is True
        assert cookie["samesite"].lower() == "lax"
        assert cookie["path"] == "/"
    assert client.get(f"/api/v1/rooms/{slug}/session").status_code == 200
    assert client.get("/api/v1/last-room").json() == {"slug": slug}


def test_wrong_password_and_unknown_room_look_the_same():
    _, slug = room()
    client = browser()
    wrong = sign_in(client, slug, "not-the-password")
    unknown = sign_in(client, "no-such-room", "pw")
    assert_error(wrong, 401, "invalid_password")
    assert_error(unknown, 401, "invalid_password")
    assert wrong.content == unknown.content
    assert "set-cookie" not in wrong.headers
    assert "set-cookie" not in unknown.headers
    assert db.execute("SELECT COUNT(*) FROM room_access_tokens").fetchone()[0] == 0


@pytest.mark.parametrize(
    "body", [{}, {"password": 123}, {"password": None}, {"password": "x" * 1025}]
)
def test_sign_in_with_a_bad_body_is_422(body):
    _, slug = room()
    response = browser().post(f"/api/v1/rooms/{slug}/session", json=body)
    assert_error(response, 422, "invalid_request")


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": HTTPS, "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_origin_sign_in_is_rejected(headers):
    _, slug = room()
    client = TestClient(main.app, base_url=HTTPS)
    response = client.post(
        f"/api/v1/rooms/{slug}/session", json={"password": "pw"}, headers=headers
    )
    assert_error(response, 403, "forbidden_origin")
    assert "set-cookie" not in response.headers
    assert db.execute("SELECT COUNT(*) FROM room_access_tokens").fetchone()[0] == 0


def test_sign_in_without_origin_is_rejected():
    _, slug = room()
    client = TestClient(main.app, base_url=HTTPS)
    response = client.post(f"/api/v1/rooms/{slug}/session", json={"password": "pw"})
    assert_error(response, 403, "forbidden_origin")


def test_sign_in_as_a_form_post_is_rejected():
    _, slug = room()
    response = browser().post(f"/api/v1/rooms/{slug}/session", data={"password": "pw"})
    assert_error(response, 415, "invalid_request")


def test_who_am_i_with_and_without_cookie():
    _, slug = room()
    client = browser()
    assert_error(client.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")
    sign_in(client, slug)
    response = client.get(f"/api/v1/rooms/{slug}/session")
    assert response.status_code == 200
    assert response.json() == {"room": {"slug": slug, "name": "Home"}}
    assert response.headers["cache-control"] == "no-store"


def test_who_am_i_shows_the_current_room_name():
    room_id, slug = room()
    client = browser()
    sign_in(client, slug)
    database_crud.rename_room(room_id, "Cabin")
    assert client.get(f"/api/v1/rooms/{slug}/session").json()["room"]["name"] == (
        "Cabin"
    )


def test_cookie_for_one_room_does_not_open_another():
    _, slug = room()
    _, other_slug = create_room("Other", "other-pw")
    client = browser()
    sign_in(client, slug)
    assert_error(
        client.get(f"/api/v1/rooms/{other_slug}/session"), 401, "not_authenticated"
    )
    # The token of one room in the other room's cookie is rejected too.
    token = client.cookies.get(token_cookie_name(slug))
    client.cookies.set(token_cookie_name(other_slug), token)
    assert_error(
        client.get(f"/api/v1/rooms/{other_slug}/session"), 401, "not_authenticated"
    )


def test_sign_out_revokes_the_token_on_the_server():
    _, slug = room()
    client = browser()
    sign_in(client, slug)
    token = client.cookies.get(token_cookie_name(slug))
    response = client.delete(f"/api/v1/rooms/{slug}/session")
    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    cleared = set_cookies(response)[token_cookie_name(slug)]
    assert cleared["max-age"] == "0" and cleared["secure"] is True
    assert cleared["path"] == "/"
    assert validate_room_access_token(slug, token) is None
    # A copy of the old cookie no longer works.
    stale = browser()
    stale.cookies.set(token_cookie_name(slug), token)
    assert_error(stale.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")


def test_sign_out_when_already_signed_out_is_204():
    _, slug = room()
    client = browser()
    assert client.delete(f"/api/v1/rooms/{slug}/session").status_code == 204
    assert client.delete("/api/v1/rooms/no-such-room/session").status_code == 204


def test_sign_out_needs_the_same_origin():
    _, slug = room()
    client = browser()
    sign_in(client, slug)
    token = client.cookies.get(token_cookie_name(slug))
    response = client.delete(
        f"/api/v1/rooms/{slug}/session", headers={"Origin": "https://evil.example"}
    )
    assert_error(response, 403, "forbidden_origin")
    assert validate_room_access_token(slug, token) is not None


def test_sign_out_cannot_revoke_a_token_of_another_room():
    _, slug = room()
    _, other_slug = create_room("Other", "other-pw")
    client = browser()
    sign_in(client, slug)
    token = client.cookies.get(token_cookie_name(slug))
    client.cookies.set(token_cookie_name(other_slug), token)
    client.delete(f"/api/v1/rooms/{other_slug}/session")
    assert validate_room_access_token(slug, token) is not None


def test_sign_out_keeps_the_cookie_when_the_database_fails(monkeypatch):
    _, slug = room()
    client = browser()
    sign_in(client, slug)

    def locked(*args: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("api.session.revoke_room_access_token", locked)
    response = client.delete(f"/api/v1/rooms/{slug}/session")
    assert_error(response, 503, "unavailable")
    assert "set-cookie" not in response.headers


def test_revoked_token_gives_401_and_clears_the_cookie():
    _, slug = room()
    client = browser()
    sign_in(client, slug)
    token = client.cookies.get(token_cookie_name(slug))
    database_crud.revoke_room_access_token(slug, token)
    response = client.get(f"/api/v1/rooms/{slug}/session")
    assert_error(response, 401, "not_authenticated")
    cleared = set_cookies(response)
    assert set(cleared) == {token_cookie_name(slug)}
    assert cleared[token_cookie_name(slug)]["max-age"] == "0"
    assert cleared[token_cookie_name(slug)]["secure"] is True
    assert token_cookie_name(slug) not in client.cookies


def test_who_am_i_keeps_the_cookie_when_the_database_fails(monkeypatch):
    _, slug = room()
    client = browser()
    sign_in(client, slug)

    def locked(*args: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(database_crud, "_valid_room_id_for_token_locked", locked)
    response = client.get(f"/api/v1/rooms/{slug}/session")
    assert_error(response, 503, "unavailable")
    assert "set-cookie" not in response.headers


def test_password_reset_revokes_api_sessions():
    room_id, slug = room()
    client = browser()
    sign_in(client, slug)
    update_room_password(room_id, "new-password")
    assert_error(client.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")
    assert_error(sign_in(client, slug, "pw"), 401, "invalid_password")
    assert sign_in(client, slug, "new-password").status_code == 200


def test_password_change_revokes_api_sessions():
    _, slug = room()
    client = browser()
    sign_in(client, slug)
    change_room_password_and_issue_token(slug, "pw", "changed")
    assert_error(client.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")


def test_last_room():
    _, slug = room()
    client = browser()
    assert client.get("/api/v1/last-room").json() == {"slug": None}
    sign_in(client, slug)
    response = client.get("/api/v1/last-room")
    assert response.json() == {"slug": slug}
    assert response.headers["cache-control"] == "no-store"
    # Routing only: it stays after signing out.
    client.delete(f"/api/v1/rooms/{slug}/session")
    assert client.get("/api/v1/last-room").json() == {"slug": slug}


def test_last_room_ignores_the_other_schemes_cookie():
    client = browser(HTTP)
    client.cookies.set(LAST_ROOM_COOKIE, "home-123456")
    assert client.get("/api/v1/last-room").json() == {"slug": None}
    client = browser()
    client.cookies.set(PLAIN_LAST_ROOM_COOKIE, "home-123456")
    assert client.get("/api/v1/last-room").json() == {"slug": None}


def test_https_ignores_plain_cookies():
    _, slug = room()
    token = authenticate_room_and_issue_token(slug, "pw")[1]
    client = browser()
    client.cookies.set(plain_token_cookie_name(slug), token)
    assert_error(client.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")


def test_nicegui_cookie_works_for_the_api_on_https():
    _, slug = room()
    token = authenticate_room_and_issue_token(slug, "pw")[1]
    client = TestClient(main.app, base_url=HTTPS)
    # NiceGUI's own cookie endpoint stores the token after a password sign-in.
    response = client.post(
        f"/_room-access/{slug}",
        json={"token": token},
        headers={"Origin": HTTPS, "X-Listapp-Request": "1"},
    )
    assert response.status_code == 204
    response = client.get(f"/api/v1/rooms/{slug}/session")
    assert response.status_code == 200
    assert response.json()["room"]["slug"] == slug
    assert client.get("/api/v1/last-room").json() == {"slug": slug}


def test_api_sign_in_cookie_is_the_one_nicegui_reads():
    _, slug = room()
    client = browser()
    sign_in(client, slug)
    token = client.cookies.get(token_cookie_name(slug))
    # NiceGUI's cookie check confirms the cookie it would read holds this token.
    response = client.post(
        f"/_room-access/{slug}",
        json={"token": token, "check": True},
        headers={"X-Listapp-Request": "1"},
    )
    assert response.status_code == 204
