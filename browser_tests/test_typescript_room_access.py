"""Request tests of the Bun room-access routes, using only disposable databases."""

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from http.cookies import Morsel, SimpleCookie
from pathlib import Path

import bcrypt
import httpx2 as httpx
import pytest

from api.version import API_VERSION, API_VERSION_HEADER
from conftest import TestServer, TypeScriptTestServer
from identifiers import token_hash
from item_names import item_name_key, register_sqlite_item_name_key
from room_cookies import (
    LAST_ROOM_COOKIE,
    PLAIN_LAST_ROOM_COOKIE,
    plain_token_cookie_name,
)

pytestmark = pytest.mark.own_server


@pytest.fixture(autouse=True)
def typescript_only(pytestconfig: pytest.Config) -> None:
    if pytestconfig.getoption("--browser-backend") != "typescript":
        pytest.skip("Run with --browser-backend typescript after bun run build:ts")


@contextmanager
def storage(server: TestServer) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(server.database)) as db, db:
        yield db


def assert_error(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].split(";", 1)[0] == "application/json"
    assert_headers(response)
    [key] = response.json()
    assert key == "error"
    error = response.json()["error"]
    assert set(error) == {"code", "message"}
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]


def set_cookies(response: httpx.Response) -> dict[str, Morsel[str]]:
    cookies = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookies.load(header)
    return dict(cookies)


def client_for(origin: str, public_origin: str | None = None) -> httpx.Client:
    return httpx.Client(base_url=origin, headers={"Origin": public_origin or origin})


def session_path(slug: str) -> str:
    return f"/api/v1/rooms/{slug}/session"


def sign_in(client: httpx.Client, slug: str, password: str) -> httpx.Response:
    return client.post(session_path(slug), json={"password": password})


def assert_headers(response: httpx.Response) -> None:
    assert response.headers[API_VERSION_HEADER] == str(API_VERSION)
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["content-security-policy"] == "frame-ancestors 'none'"


def assert_sign_in(response: httpx.Response, slug: str, *, secure: bool) -> str:
    assert response.status_code == 200
    assert response.json() == {"room": {"slug": slug, "name": "Home"}}
    assert_headers(response)
    cookies = set_cookies(response)
    last_name = LAST_ROOM_COOKIE if secure else PLAIN_LAST_ROOM_COOKIE
    token_name = ("__Host-" if secure else "") + plain_token_cookie_name(slug)
    assert set(cookies) == {token_name, last_name}
    for cookie in cookies.values():
        assert bool(cookie["secure"]) is secure
        assert cookie["httponly"]
        assert cookie["path"] == "/"
        assert cookie["samesite"].lower() == "lax"
        assert cookie["max-age"] == "31536000"
        assert not cookie["domain"]
    assert cookies[last_name].value == slug
    token = cookies[token_name].value
    assert len(token) == 43
    assert token not in response.text
    return token


def add_enrollment(
    db: sqlite3.Connection, room_id: int, token: str, status: str
) -> int:
    installation_id = db.execute(
        "INSERT INTO reminder_installations (secret_hash, timezone, created_at, expires_at) "
        "VALUES (?, 'UTC', CURRENT_TIMESTAMP, '2099-01-01') RETURNING id",
        (uuid.uuid4().hex,),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO reminder_enrollments (installation_id, room_id, token_hash, "
        "authorization_version, status, activated_at, expires_at, created_at) "
        "VALUES (?, ?, ?, 1, ?, CURRENT_TIMESTAMP, '2099-01-01', CURRENT_TIMESTAMP)",
        (installation_id, room_id, token_hash(token), status),
    )
    return installation_id


def grants(server: TestServer) -> list[tuple[str, int]]:
    return server.query(
        "SELECT status, revision FROM reminder_enrollments ORDER BY installation_id"
    )


def test_python_cookie_and_short_password_work_on_a_bun_copy(tmp_path: Path) -> None:
    # obligation: rule-success.SignInToRoom
    # obligation: rule-failure.SignInToRoom.2
    # obligation: rule-entity-creation.SignInToRoom.1
    # obligation: surface-actor.SignIn
    # obligation: surface-provides.SignIn
    # obligation: entity-fields.Room
    # obligation: entity-fields.RoomSession
    # obligation: surface-exposure.PrivateRoom
    python_dir = tmp_path / "python"
    bun_dir = tmp_path / "bun"
    python_dir.mkdir()
    bun_dir.mkdir()
    reference = TestServer(python_dir)
    bun = TypeScriptTestServer(bun_dir)
    legacy = " ø "  # Short, UTF-8, and the outer spaces matter.
    try:
        reference.start()
        slug = reference.room_slug
        with storage(reference) as db:
            db.execute(
                "UPDATE rooms SET password_hash = ? WHERE slug = ?",
                (
                    bcrypt.hashpw(legacy.encode(), bcrypt.gensalt(rounds=4)).decode(),
                    slug,
                ),
            )
        with client_for(reference.url) as client:
            old_token = assert_sign_in(
                sign_in(client, slug, legacy), slug, secure=False
            )
            assert_error(sign_in(client, slug, legacy.strip()), 401, "invalid_password")
        with (
            storage(reference) as db,
            closing(sqlite3.connect(bun.database)) as copy,
        ):
            db.backup(copy)

        bun.start()
        with client_for(bun.url) as client:
            client.cookies.set(plain_token_cookie_name(slug), old_token)
            response = client.get(session_path(slug))
            assert response.status_code == 200
            assert response.json() == {"room": {"slug": slug, "name": "Home"}}
            assert_error(sign_in(client, slug, legacy.strip()), 401, "invalid_password")
            new_token = assert_sign_in(
                sign_in(client, slug, legacy), slug, secure=False
            )
            assert new_token != old_token
        assert bun.query(
            "SELECT authorization_version FROM room_access_tokens WHERE token_hash = ?",
            (token_hash(new_token),),
        ) == [(1,)]
    finally:
        bun.stop()
        reference.stop()


def test_https_cookie_names_are_separate_from_plain_http(tmp_path: Path) -> None:
    server = TypeScriptTestServer(tmp_path)
    public_origin = "https://list.test"
    server.env["LISTR_TS_ORIGIN"] = public_origin
    try:
        server.start()
        slug = server.room_slug
        plain = plain_token_cookie_name(slug)
        with client_for(server.url, public_origin) as client:
            token = assert_sign_in(
                sign_in(client, slug, server.password), slug, secure=True
            )
            assert_error(
                client.get(session_path(slug), headers={"Cookie": f"{plain}={token}"}),
                401,
                "not_authenticated",
            )
            header = {"Cookie": f"__Host-{plain}={token}; {LAST_ROOM_COOKIE}={slug}"}
            assert client.get(session_path(slug), headers=header).status_code == 200
            assert client.get("/api/v1/last-room", headers=header).json() == {
                "slug": slug
            }
            signed_out = client.delete(session_path(slug), headers=header)
            assert signed_out.status_code == 204
            cleared = set_cookies(signed_out)[f"__Host-{plain}"]
            assert (
                cleared["secure"] and cleared["httponly"] and cleared["max-age"] == "0"
            )
    finally:
        server.stop()


def test_room_keeps_newest_200_tokens_and_checks_their_version(
    server: TypeScriptTestServer,
) -> None:
    slug = server.room_slug
    room_id, version = server.query(
        "SELECT id, authorization_version FROM rooms WHERE slug = ?", (slug,)
    )[0]
    with storage(server) as db:
        db.executemany(
            "INSERT INTO room_access_tokens (room_id, token_hash, authorization_version) "
            "VALUES (?, ?, ?)",
            [(room_id, token_hash(f"old-token-{i}"), version) for i in range(200)],
        )
    name = plain_token_cookie_name(slug)
    oldest = {"Cookie": f"{name}=old-token-0"}
    next_oldest = {"Cookie": f"{name}=old-token-1"}
    with client_for(server.url) as client:
        assert client.get(session_path(slug), headers=oldest).status_code == 200
        assert sign_in(client, slug, server.password).status_code == 200
        assert_error(
            client.get(session_path(slug), headers=oldest), 401, "not_authenticated"
        )
        assert client.get(session_path(slug), headers=next_oldest).status_code == 200
        assert server.query("SELECT COUNT(*) FROM room_access_tokens") == [(200,)]
        # A stale version must never grant access even if its token row remains.
        with storage(server) as db:
            db.execute(
                "UPDATE rooms SET authorization_version = authorization_version + 1"
            )
        assert_error(
            client.get(session_path(slug), headers=next_oldest),
            401,
            "not_authenticated",
        )


def test_write_admission_and_api_errors(server: TypeScriptTestServer) -> None:
    # SignIn.SameOriginWrites: admission runs before credential and body checks.
    slug = server.room_slug
    path = f"/api/v1/rooms/{slug}"
    with client_for(server.url) as client:
        for method, url in [
            ("POST", session_path(slug)),
            ("DELETE", session_path(slug)),
            ("POST", f"{path}/password"),
            ("DELETE", path),
        ]:
            response = client.request(
                method,
                url,
                headers={"Origin": "https://other.test"},
                data={"password": "x"},
            )
            assert_error(response, 403, "forbidden_origin")
            assert_headers(response)
        for headers in [{}, {"Origin": server.url, "Sec-Fetch-Site": "same-site"}]:
            response = httpx.post(
                server.url + session_path(slug), headers=headers, json={}
            )
            assert_error(response, 403, "forbidden_origin")
        target = session_path(slug)
        assert_error(
            client.post(target, data={"password": "x"}), 415, "invalid_request"
        )
        json_headers = {"Content-Type": "application/json; charset=UTF-8"}
        for body, status in [(b"[", 400), (b"[]", 422), (b"x" * 65537, 413)]:
            response = client.post(target, content=body, headers=json_headers)
            assert_error(response, status, "invalid_request")
        for body in [
            {},
            {"password": 3},
            {"password": "x" * 1025},
            {"password": "x", "extra": 1},
        ]:
            assert_error(client.post(target, json=body), 422, "invalid_request")
        assert_error(
            client.post(
                target, content=b'{"password":"\\ud800"}', headers=json_headers
            ),
            422,
            "invalid_request",
        )
        assert_error(client.delete(path), 400, "invalid_request")
        wrong_method = client.get(path)
        assert_error(wrong_method, 405, "invalid_request")
        assert "DELETE" in wrong_method.headers["allow"]
        unknown = client.get("/api/v1/no-such-path")
        assert_error(unknown, 404, "not_found")
        assert_headers(unknown)
    assert server.query("SELECT id FROM room_access_tokens") == []


def test_temporary_sign_in_failure_returns_both_slots(
    server: TypeScriptTestServer,
) -> None:
    # obligation: rule-failure.SignInToRoom.1
    # The approved exception is Bun room-only, and is not compared to Python.
    slug = server.room_slug
    with client_for(server.url) as client:
        wrong = sign_in(client, slug, "wrong")
        assert_error(wrong, 401, "invalid_password")
        for _ in range(10):
            unknown = sign_in(client, "unknown-one", "wrong")
            assert unknown.json() == wrong.json()
            assert_error(unknown, 401, "invalid_password")
        refused = sign_in(client, "unknown-one", "wrong")
        assert_error(refused, 429, "too_many_attempts")
        assert 1 <= int(refused.headers["retry-after"]) <= 60
        for _ in range(8):
            assert_error(sign_in(client, slug, "wrong"), 401, "invalid_password")
        for _ in range(10):
            assert_error(
                sign_in(client, "unknown-two", "wrong"), 401, "invalid_password"
            )
        # Home is at 9/10; all rooms are at 29/30. A failed insert is temporary.
        with storage(server) as db:
            db.execute(
                "CREATE TRIGGER fail_sign_in BEFORE INSERT ON room_access_tokens "
                "BEGIN SELECT RAISE(ABORT, 'injected sign-in failure'); END"
            )
        for _ in range(2):
            failed = sign_in(client, slug, server.password)
            assert_error(failed, 503, "unavailable")
            assert "set-cookie" not in failed.headers
        assert server.query("SELECT id FROM room_access_tokens") == []
        with storage(server) as db:
            db.execute("DROP TRIGGER fail_sign_in")
        assert sign_in(client, slug, server.password).status_code == 200
        assert_error(sign_in(client, slug, "wrong"), 401, "invalid_password")
        for name in [slug, "another-unknown"]:
            refused = sign_in(client, name, server.password)
            assert_error(refused, 429, "too_many_attempts")
            assert 1 <= int(refused.headers["retry-after"]) <= 60


def test_sign_out_revokes_only_the_presented_room_token(
    server: TypeScriptTestServer,
) -> None:
    # obligation: rule-success.SignOutOfRoom
    # obligation: surface-actor.PrivateRoom
    # obligation: surface-provides.PrivateRoom
    slug = server.room_slug
    room_id = server.query("SELECT id FROM rooms WHERE slug = ?", (slug,))[0][0]
    with client_for(server.url) as a, client_for(server.url) as b:
        token_a = assert_sign_in(sign_in(a, slug, server.password), slug, secure=False)
        token_b = assert_sign_in(sign_in(b, slug, server.password), slug, secure=False)
        name = plain_token_cookie_name(slug)
        old = {"Cookie": f"{name}={token_a}"}
        with storage(server) as db:
            add_enrollment(db, room_id, token_a, "active")
            add_enrollment(db, room_id, token_b, "active")
            add_enrollment(db, room_id, token_a, "opted_out")
            db.execute(
                "CREATE TRIGGER fail_cutoff BEFORE UPDATE ON reminder_enrollments "
                "BEGIN SELECT RAISE(ABORT, 'injected enrollment failure'); END"
            )
        failed = a.delete(session_path(slug))
        assert_error(failed, 503, "unavailable")
        assert "set-cookie" not in failed.headers
        assert a.get(session_path(slug)).status_code == 200
        assert grants(server) == [("active", 1), ("active", 1), ("opted_out", 1)]
        with storage(server) as db:
            db.execute("DROP TRIGGER fail_cutoff")
        assert (
            a.delete(
                session_path("another-room"),
                headers={
                    "Cookie": f"{plain_token_cookie_name('another-room')}={token_a}"
                },
            ).status_code
            == 204
        )
        assert a.get(session_path(slug)).status_code == 200
        for _ in range(2):
            done = a.delete(session_path(slug), headers=old)
            assert done.status_code == 204 and not done.content
            assert_headers(done)
            assert set_cookies(done)[name]["max-age"] == "0"
        assert a.delete(session_path(slug)).status_code == 204
        assert grants(server) == [("revoked", 2), ("active", 1), ("opted_out", 1)]
        revoked = a.get(session_path(slug), headers=old)
        assert_error(revoked, 401, "not_authenticated")
        assert set_cookies(revoked)[name]["max-age"] == "0"
        assert b.get(session_path(slug)).status_code == 200
        assert a.get("/api/v1/last-room").json() == {"slug": slug}
        assert_error(a.get(session_path(slug)), 401, "not_authenticated")
        assert_error(a.get(session_path("another-room")), 401, "not_authenticated")


def test_password_change_replaces_all_tokens_and_cuts_active_enrollments(
    server: TypeScriptTestServer,
) -> None:
    # obligation: rule-success.ChangeRoomPassword
    # obligation: rule-failure.ChangeRoomPassword.1
    # obligation: rule-failure.ChangeRoomPassword.2
    # obligation: rule-failure.ChangeRoomPassword.3
    # obligation: rule-entity-creation.ChangeRoomPassword.1
    # obligation: derived.RoomSession.current
    slug = server.room_slug
    room_id = server.query("SELECT id FROM rooms WHERE slug = ?", (slug,))[0][0]
    path = f"/api/v1/rooms/{slug}/password"
    replacement = " " + "ø" * 35 + " "  # Exactly 72 UTF-8 bytes, saved as typed.
    change = {"current_password": server.password, "new_password": replacement}
    with client_for(server.url) as a, client_for(server.url) as b:
        assert_error(a.post(path, json=change), 401, "not_authenticated")
        ta = assert_sign_in(sign_in(a, slug, server.password), slug, secure=False)
        tb = assert_sign_in(sign_in(b, slug, server.password), slug, secure=False)
        with storage(server) as db:
            add_enrollment(db, room_id, ta, "active")
            add_enrollment(db, room_id, tb, "active")
            add_enrollment(db, room_id, ta, "opted_out")
        bad = a.post(path, json={**change, "current_password": "wrong"})
        assert_error(bad, 403, "wrong_password")
        assert bad.json()["error"]["message"] == "Incorrect current password"
        for invalid in ["   ", "abc", replacement + "x"]:
            assert_error(
                a.post(path, json={**change, "new_password": invalid}),
                422,
                "invalid_request",
            )
        assert grants(server) == [("active", 1), ("active", 1), ("opted_out", 1)]
        new_token = assert_sign_in(a.post(path, json=change), slug, secure=False)
        assert new_token not in {ta, tb}
        assert a.get(session_path(slug)).status_code == 200
        assert_error(b.get(session_path(slug)), 401, "not_authenticated")
        assert_error(sign_in(b, slug, server.password), 401, "invalid_password")
        assert_error(sign_in(b, slug, replacement + "x"), 401, "invalid_password")
    [(hash_text, version)] = server.query(
        "SELECT password_hash, authorization_version FROM rooms WHERE slug = ?", (slug,)
    )
    assert version == 2
    assert bcrypt.checkpw(replacement.encode(), hash_text.encode())
    assert server.query(
        "SELECT token_hash, authorization_version FROM room_access_tokens"
    ) == [(token_hash(new_token), 2)]
    assert grants(server) == [("revoked", 2), ("revoked", 2), ("opted_out", 1)]
    assert server.query("SELECT * FROM processed_ops") == []
    with client_for(server.url) as browser:
        assert sign_in(browser, slug, replacement).status_code == 200


def test_room_delete_cascades_or_rolls_back_as_one_write(
    server: TypeScriptTestServer,
) -> None:
    # obligation: rule-success.DeleteRoomAsParticipant
    # obligation: rule-failure.DeleteRoomAsParticipant.1
    # obligation: rule-failure.DeleteRoomAsParticipant.2
    slug = server.room_slug
    path = f"/api/v1/rooms/{slug}"
    room_id = server.query("SELECT id FROM rooms WHERE slug = ?", (slug,))[0][0]
    body = {"password": server.password}
    with client_for(server.url) as a, client_for(server.url) as b:
        assert_error(a.request("DELETE", path, json=body), 401, "not_authenticated")
        ta = assert_sign_in(sign_in(a, slug, server.password), slug, secure=False)
        assert sign_in(b, slug, server.password).status_code == 200
        bad = a.request("DELETE", path, json={"password": "wrong"})
        assert_error(bad, 403, "wrong_password")
        with storage(server) as db:
            register_sqlite_item_name_key(db)
            add_enrollment(db, room_id, ta, "active")
            list_id = db.execute(
                "INSERT INTO lists (name, slug, room_id, uid, share_token) "
                "VALUES ('List', 'list-test', ?, ?, 'test-share') RETURNING id",
                (room_id, str(uuid.uuid4())),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO items (name, name_key, done, list_id, uid, added_at) "
                "VALUES ('Milk', ?, 0, ?, ?, CURRENT_TIMESTAMP)",
                (item_name_key("Milk"), list_id, str(uuid.uuid4())),
            )
            db.execute(
                "CREATE TRIGGER fail_delete BEFORE DELETE ON rooms "
                "BEGIN SELECT RAISE(ABORT, 'injected delete failure'); END"
            )
        failed = a.request("DELETE", path, json=body)
        assert_error(failed, 503, "unavailable")
        assert "set-cookie" not in failed.headers
        assert a.get(session_path(slug)).status_code == 200
        assert server.query("SELECT name FROM items") == [("Milk",)]
        assert grants(server) == [("active", 1)]
        with storage(server) as db:
            db.execute("DROP TRIGGER fail_delete")
        done = a.request("DELETE", path, json=body)
        assert done.status_code == 204 and not done.content
        assert set(set_cookies(done)) == {
            plain_token_cookie_name(slug),
            PLAIN_LAST_ROOM_COOKIE,
        }
        assert a.get("/api/v1/last-room").json() == {"slug": None}
        assert_error(b.get(session_path(slug)), 401, "not_authenticated")
    for table in (
        "rooms",
        "lists",
        "items",
        "room_access_tokens",
        "reminder_enrollments",
        "deletions",
    ):
        assert server.query(f"SELECT * FROM {table}") == [], table
    assert server.query("PRAGMA foreign_key_check") == []
