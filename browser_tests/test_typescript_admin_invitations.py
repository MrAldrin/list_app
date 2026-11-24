"""Bun admin and invitation boundaries on disposable SQLite databases."""

import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import httpx2 as httpx
import pytest
from test_typescript_room_access import (
    add_enrollment,
    assert_error,
    assert_headers,
    client_for,
    grants,
    session_path,
    set_cookies,
    sign_in,
    storage,
)

from admin_access import issue_admin_token
from conftest import TypeScriptTestServer
from identifiers import token_hash
from item_names import item_name_key, register_sqlite_item_name_key
from room_cookies import PLAIN_LAST_ROOM_COOKIE, plain_token_cookie_name

pytestmark = pytest.mark.own_server

ADMIN = "/api/v1/admin/session"
ROOMS = "/api/v1/admin/rooms"
INVITATIONS = "/api/v1/admin/invitations"
COOKIE = "listapp-admin"
SESSION_SECONDS = 30 * 60
WEEK = 7 * 24 * 60 * 60


@pytest.fixture(autouse=True)
def typescript_only(pytestconfig: pytest.Config) -> None:
    if pytestconfig.getoption("--browser-backend") != "typescript":
        pytest.skip("Run with --browser-backend typescript after bun run build:ts")


def admin_sign_in(client: httpx.Client, password: str) -> str:
    start = int(time.time())
    response = client.post(ADMIN, json={"password": password})
    assert response.status_code == 200
    assert response.json() == {}
    assert_headers(response)
    [cookie] = set_cookies(response).values()
    assert cookie.key in {COOKIE, f"__Host-{COOKIE}"}
    assert bool(cookie["secure"]) is cookie.key.startswith("__Host-")
    assert cookie["httponly"] and not cookie["domain"]
    assert cookie["path"] == "/" and cookie["samesite"].lower() == "lax"
    assert cookie["max-age"] == str(SESSION_SECONDS)
    match = re.fullmatch(r"v2\.([0-9]+)\.[0-9a-f]{32}\.[0-9a-f]{64}", cookie.value)
    assert match is not None
    assert (
        start + SESSION_SECONDS <= int(match[1]) <= int(time.time()) + SESSION_SECONDS
    )
    return cookie.value


def issue(client: httpx.Client) -> tuple[int, str]:
    response = client.post(INVITATIONS, json={})
    assert response.status_code == 200, response.text
    assert_headers(response)
    assert "set-cookie" not in response.headers
    issued = response.json()
    assert set(issued) == {"invitation", "token"}
    entry, token = issued["invitation"], issued["token"]
    assert set(entry) == {"id", "status", "created_at", "expires_at", "revoked_at"}
    assert entry["status"] == "active" and entry["revoked_at"] is None
    assert re.fullmatch(r"[a-zA-Z0-9_-]{43}", token)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", entry["created_at"])
    created = datetime.fromisoformat(entry["created_at"])
    assert created.tzinfo is UTC
    assert datetime.fromisoformat(entry["expires_at"]) - created == timedelta(days=7)
    return entry["id"], token


def test_admin_cookie_expiry_and_sign_out_scope(
    server: TypeScriptTestServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    # obligation: entity-fields.AdminSession
    # obligation: derived.AdminSession.current
    # obligation: config-default.admin_duration
    # obligation: rule-success.SignInAsAdmin
    # obligation: rule-entity-creation.SignInAsAdmin.1
    # obligation: surface-actor.SignIn
    # obligation: surface-provides.SignIn
    # SignIn.BrowserCookies and AdminTools.SeparateAdminAccess.
    slug = server.room_slug
    monkeypatch.setenv("APP_PASSWORD", server.password)
    # Only the v2 cookie format crosses servers. Build a valid, already expired
    # cookie instead of waiting 30 minutes or modifying a signature by hand.
    old = issue_admin_token()
    expired = issue_admin_token(now=time.time() - SESSION_SECONDS)
    monkeypatch.setenv("APP_PASSWORD", "previous-test-app-password")
    rotated = issue_admin_token()

    with client_for(server.url) as a, client_for(server.url) as b:
        token_a = admin_sign_in(a, server.password)
        token_b = admin_sign_in(b, server.password)
        assert token_a != token_b
        for path in (ADMIN, ROOMS, INVITATIONS):
            response = a.get(path)
            assert response.status_code == 200
            assert "set-cookie" not in response.headers
        assert a.get(ADMIN, headers={"Cookie": f"{COOKIE}={old}"}).status_code == 200
        wrong = a.post(ADMIN, json={"password": f" {server.password} "})
        assert_error(wrong, 401, "invalid_password")
        assert wrong.json()["error"]["message"] == "Wrong password"
        assert "set-cookie" not in wrong.headers
        assert a.get(ADMIN).status_code == 200
        assert_error(a.get(session_path(slug)), 401, "not_authenticated")
        assert sign_in(a, slug, server.password).status_code == 200
        done = a.delete(ADMIN)
        assert done.status_code == 204 and not done.content
        assert_headers(done)
        assert set(set_cookies(done)) == {COOKIE}
        assert set_cookies(done)[COOKIE]["max-age"] == "0"
        assert a.get(session_path(slug)).status_code == 200
        assert b.get(ADMIN).status_code == 200
        assert_error(a.get(ADMIN), 401, "admin_required")
        assert a.delete(ADMIN).status_code == 204

    tampered = old[:-1] + ("0" if old[-1] != "0" else "1")
    with client_for(server.url) as browser:
        for bad_token in (expired, rotated, tampered, old.replace("v2.", "v1.", 1)):
            response = browser.get(ADMIN, headers={"Cookie": f"{COOKIE}={bad_token}"})
            assert_error(response, 401, "admin_required")
            assert set_cookies(response)[COOKIE]["max-age"] == "0"
        assert "set-cookie" not in browser.get(ADMIN).headers
        assert_error(
            browser.get(ADMIN, headers={"Cookie": f"__Host-{COOKIE}={old}"}),
            401,
            "admin_required",
        )


def test_https_admin_cookie_and_clear_use_only_https_name(tmp_path: Path) -> None:
    server = TypeScriptTestServer(tmp_path)
    origin = "https://list.test"
    server.env["LISTR_TS_ORIGIN"] = origin
    try:
        server.start()
        with client_for(server.url, origin) as client:
            token = admin_sign_in(client, server.password)
            assert_error(
                client.get(ADMIN, headers={"Cookie": f"{COOKIE}={token}"}),
                401,
                "admin_required",
            )
            headers = {"Cookie": f"__Host-{COOKIE}={token}"}
            assert client.get(ADMIN, headers=headers).status_code == 200
            cleared = set_cookies(client.delete(ADMIN, headers=headers))
            assert set(cleared) == {f"__Host-{COOKIE}"}
            [cookie] = cleared.values()
            assert cookie["secure"] and cookie["httponly"] and not cookie["domain"]
            assert cookie["path"] == "/" and cookie["samesite"].lower() == "lax"
            assert cookie["max-age"] == "0"
    finally:
        server.stop()


def test_admin_sign_in_has_a_separate_shared_limit(
    server: TypeScriptTestServer,
) -> None:
    # obligation: rule-failure.SignInAsAdmin.1
    # obligation: rule-failure.SignInAsAdmin.2
    # SignIn.PasswordsAndAttemptLimits: success gives its slot back.
    with client_for(server.url) as a, client_for(server.url) as b:
        for i in range(9):
            browser = a if i % 2 == 0 else b
            wrong = browser.post(ADMIN, json={"password": "wrong"})
            assert_error(wrong, 401, "invalid_password")
            assert "set-cookie" not in wrong.headers
        admin_sign_in(a, server.password)
        admin_sign_in(b, server.password)
        assert_error(b.post(ADMIN, json={"password": "wrong"}), 401, "invalid_password")
        for browser in (a, b):
            response = browser.post(ADMIN, json={"password": server.password})
            assert_error(response, 429, "too_many_attempts")
            assert 1 <= int(response.headers["retry-after"]) <= 60
            assert "set-cookie" not in response.headers
        assert sign_in(b, server.room_slug, server.password).status_code == 200


def test_admin_checks_auth_before_bodies_and_targets(
    server: TypeScriptTestServer,
) -> None:
    # obligation: rule-failure.ResetRoomPasswordAsAdmin.1
    # obligation: rule-failure.DeleteRoomAsAdmin.1
    # obligation: rule-failure.IssueRoomInvitation.1
    # obligation: rule-failure.RevokeRoomInvitation.1
    # obligation: rule-failure.ReadInvitationHistory.1
    # obligation: rule-failure.CreateRoomAsAdmin.1
    # obligation: surface-actor.AdminTools
    # obligation: surface-actor.Administration
    # SignIn.SameOriginWrites: the shared admission guard still runs first.
    with client_for(server.url) as client:
        assert sign_in(client, server.room_slug, server.password).status_code == 200
        for path in (ROOMS, INVITATIONS):
            assert_error(client.get(path), 401, "admin_required")
        writes = (
            ("POST", ROOMS),
            ("POST", f"{ROOMS}/not-a-room/password"),
            ("DELETE", f"{ROOMS}/not-a-room"),
            ("POST", INVITATIONS),
            ("POST", f"{INVITATIONS}/not-an-id/revoke"),
        )
        headers = {"Content-Type": "application/json"}
        for method, url in writes:
            denied = client.request(method, url, content=b"[", headers=headers)
            assert_error(denied, 401, "admin_required")
        for method, url in (
            *writes,
            ("POST", ADMIN),
            ("DELETE", ADMIN),
            ("POST", "/api/v1/invitations/unknown/rooms"),
        ):
            denied = client.request(
                method, url, content=b"[", headers={"Origin": "https://elsewhere.test"}
            )
            assert_error(denied, 403, "forbidden_origin")
            assert "set-cookie" not in denied.headers
        assert_error(
            client.post(ADMIN, data={"password": "wrong"}), 415, "invalid_request"
        )


def test_admin_creates_sorted_room_overview_without_room_access(
    server: TypeScriptTestServer,
) -> None:
    # obligation: rule-success.CreateRoomAsAdmin
    # obligation: rule-failure.CreateRoomAsAdmin.2
    # obligation: rule-failure.CreateRoomAsAdmin.3
    # obligation: rule-entity-creation.CreateRoomAsAdmin.1
    # obligation: config-default.room_name_limit
    # obligation: config-default.initial_password_revision
    with client_for(server.url) as admin:
        admin_sign_in(admin, server.password)
        for name, password, message in (
            (" \t", "cabin-pw", "Room name cannot be empty"),
            ("ø" * 101, "cabin-pw", "Room name can be at most 100 characters"),
            ("Cabin", "abc", "Password must be at least 4 characters"),
        ):
            response = admin.post(ROOMS, json={"name": name, "password": password})
            assert_error(response, 422, "invalid_request")
            assert response.json()["error"]["message"] == message
        created = admin.post(ROOMS, json={"name": "  cabin  ", "password": " x y "})
        assert created.status_code == 200
        assert "set-cookie" not in created.headers
        room = created.json()["room"]
        slug = room["slug"]
        assert re.fullmatch(r"cabin-[0-9a-f]{6}", slug)
        assert room == {"slug": slug, "name": "cabin"}
        assert admin.get(ROOMS).json() == {
            "rooms": [room, {"slug": server.room_slug, "name": "Home"}]
        }
        assert server.query(
            "SELECT authorization_version FROM rooms WHERE slug = ?", (slug,)
        ) == [(1,)]
        assert_error(admin.get(session_path(slug)), 401, "not_authenticated")
        assert_error(sign_in(admin, slug, "x y"), 401, "invalid_password")
        assert sign_in(admin, slug, " x y ").status_code == 200


def test_admin_reset_and_delete_reuse_room_lifecycle(
    server: TypeScriptTestServer,
) -> None:
    # obligation: rule-success.ResetRoomPasswordAsAdmin
    # obligation: rule-failure.ResetRoomPasswordAsAdmin.2
    # obligation: rule-success.DeleteRoomAsAdmin
    # obligation: surface-provides.AdminTools
    slug = server.room_slug
    room = f"{ROOMS}/{slug}"
    uri = session_path(slug)
    cookie = plain_token_cookie_name(slug)
    with (
        client_for(server.url) as admin,
        client_for(server.url) as a,
        client_for(server.url) as b,
    ):
        admin_sign_in(admin, server.password)
        ta = set_cookies(sign_in(a, slug, server.password))[cookie].value
        tb = set_cookies(sign_in(b, slug, server.password))[cookie].value
        [(room_id,)] = server.query("SELECT id FROM rooms WHERE slug = ?", (slug,))
        with storage(server) as db:
            add_enrollment(db, room_id, ta, "active")
            add_enrollment(db, room_id, tb, "active")
            add_enrollment(db, room_id, tb, "opted_out")
            register_sqlite_item_name_key(db)
            [list_id] = db.execute(
                "INSERT INTO lists (name, slug, room_id, uid, share_token) "
                "VALUES ('List', 'list', ?, ?, 'test-share') RETURNING id",
                (room_id, str(uuid.uuid4())),
            ).fetchone()
            db.execute(
                "INSERT INTO items (name, name_key, done, list_id, uid, added_at) "
                "VALUES ('Milk', ?, 0, ?, ?, CURRENT_TIMESTAMP)",
                (item_name_key("Milk"), list_id, str(uuid.uuid4())),
            )
        invitation_id, _ = issue(admin)
        assert_error(
            admin.post(f"{room}/password", json={"new_password": " "}),
            422,
            "invalid_request",
        )
        assert grants(server) == [("active", 1), ("active", 1), ("opted_out", 1)]
        replacement = " reset-pw "
        done = admin.post(f"{room}/password", json={"new_password": replacement})
        assert done.status_code == 200 and done.json() == {}
        assert "set-cookie" not in done.headers
        assert server.query("SELECT authorization_version FROM rooms") == [(2,)]
        assert server.query("SELECT id FROM room_access_tokens") == []
        assert grants(server) == [("revoked", 2), ("revoked", 2), ("opted_out", 1)]
        assert (
            server.query("SELECT timezone FROM reminder_installations")
            == [("UTC",)] * 3
        )
        assert server.query("SELECT share_token FROM lists") == [("test-share",)]
        for browser in (admin, a, b):
            assert_error(browser.get(uri), 401, "not_authenticated")
        assert_error(sign_in(a, slug, server.password), 401, "invalid_password")
        assert sign_in(admin, slug, replacement).status_code == 200
        assert sign_in(b, slug, replacement).status_code == 200
        done = admin.delete(room)
        assert done.status_code == 204 and not done.content
        assert set(set_cookies(done)) == {cookie, PLAIN_LAST_ROOM_COOKIE}
        assert admin.get(ADMIN).status_code == 200
        assert admin.get("/api/v1/last-room").json() == {"slug": None}
        assert_error(b.get(uri), 401, "not_authenticated")
        assert_error(admin.delete(room), 404, "room_unavailable")
        assert_error(
            admin.post(f"{room}/password", json={"new_password": replacement}),
            404,
            "room_unavailable",
        )
    for table in (
        "rooms",
        "lists",
        "items",
        "room_access_tokens",
        "reminder_enrollments",
    ):
        assert server.query(f"SELECT * FROM {table}") == []
    assert server.query("SELECT id FROM room_invitations") == [(invitation_id,)]
    assert server.query("PRAGMA foreign_key_check") == []


def test_invitation_history_retention_and_public_errors(
    server: TypeScriptTestServer,
) -> None:
    # obligation: entity-fields.RoomInvitation
    # obligation: entity-optional.RoomInvitation.revoked_at
    # obligation: derived.RoomInvitation.usable
    # obligation: config-default.invitation_duration
    # obligation: config-default.inactive_history
    # obligation: rule-success.IssueRoomInvitation
    # obligation: rule-entity-creation.IssueRoomInvitation.1
    # obligation: rule-success.RevokeRoomInvitation
    # obligation: rule-failure.RevokeRoomInvitation.2
    # obligation: rule-success.ReadInvitationHistory
    # obligation: rule-failure.CreateRoomFromInvitation.1
    # obligation: surface-provides.Administration
    now = int(time.time())
    with client_for(server.url) as admin, client_for(server.url) as visitor:
        admin_sign_in(admin, server.password)
        assert admin.get(INVITATIONS).json() == {"invitations": []}
        expired_id, expired_token = issue(admin)
        revoked_id, revoked_token = issue(admin)
        with storage(server) as db:
            db.execute(
                "UPDATE room_invitations SET expires_at = ? WHERE id = ?",
                (now, expired_id),
            )
        assert visitor.get(f"/api/v1/invitations/{revoked_token}").status_code == 200
        revoke = f"{INVITATIONS}/{revoked_id}/revoke"
        assert admin.post(revoke, json={}).json() == {}
        assert_error(
            visitor.get(f"/api/v1/invitations/{revoked_token}"),
            404,
            "invitation_unavailable",
        )
        before = server.query(
            "SELECT revoked_at FROM room_invitations WHERE id = ?", (revoked_id,)
        )
        assert admin.post(revoke, json={}).json() == {}
        assert admin.post(f"{INVITATIONS}/{2**63 - 1}/revoke", json={}).json() == {}
        assert before == server.query(
            "SELECT revoked_at FROM room_invitations WHERE id = ?", (revoked_id,)
        )
        for bad_id in ("0", "nan", str(2**63)):
            assert_error(
                admin.post(f"{INVITATIONS}/{bad_id}/revoke", json={}),
                422,
                "invalid_request",
            )
        assert_error(
            admin.post(INVITATIONS, json={"extra": True}), 422, "invalid_request"
        )
        assert_error(admin.post(revoke, json={"extra": True}), 422, "invalid_request")
        active_id, active_token = issue(admin)
        assert server.query("SELECT token_hash FROM room_invitations ORDER BY id") == [
            (token_hash(token),)
            for token in (expired_token, revoked_token, active_token)
        ]
        listed = admin.get(INVITATIONS)
        assert listed.status_code == 200
        assert [
            (entry["id"], entry["status"]) for entry in listed.json()["invitations"]
        ] == [(active_id, "active"), (revoked_id, "revoked"), (expired_id, "expired")]
        for token in (expired_token, revoked_token, active_token):
            assert token not in listed.text and token_hash(token) not in listed.text
        for token in (expired_token, revoked_token, "no-such-token"):
            response = visitor.get(f"/api/v1/invitations/{token}")
            assert_error(response, 404, "invitation_unavailable")
            assert response.json() == {
                "error": {
                    "code": "invitation_unavailable",
                    "message": "This invitation is invalid or no longer active.",
                }
            }
            submit = visitor.post(
                f"/api/v1/invitations/{token}/rooms",
                json={"name": "Late", "password": "late-pw"},
            )
            assert submit.status_code == 404 and submit.json() == response.json()
        with storage(server) as db:
            db.execute(
                "UPDATE room_invitations SET expires_at = ? WHERE id = ?",
                (now, revoked_id),
            )
        assert admin.get(INVITATIONS).json()["invitations"][1]["status"] == "revoked"
        with storage(server) as db:
            db.execute(
                "UPDATE room_invitations SET expires_at = ? WHERE id = ?",
                (now - WEEK, revoked_id),
            )
            db.execute(
                "UPDATE room_invitations SET expires_at = ?, revoked_at = ? WHERE id = ?",
                (now + WEEK, now - WEEK, expired_id),
            )
        listed = admin.get(INVITATIONS).json()["invitations"]
        assert [entry["id"] for entry in listed] == [active_id]
        with storage(server) as db:
            db.execute(
                "UPDATE room_invitations SET expires_at = ? WHERE id = ?",
                (now - WEEK, active_id),
            )
        _, fresh_token = issue(admin)
        assert server.query("SELECT token_hash FROM room_invitations") == [
            (token_hash(fresh_token),)
        ]
        assert_error(
            visitor.get(f"/api/v1/invitations/{active_token}"),
            404,
            "invitation_unavailable",
        )
        assert server.query("SELECT name FROM rooms") == [("Home",)]


def test_invitation_creation_is_atomic_and_stops_at_five(
    server: TypeScriptTestServer,
) -> None:
    # obligation: config-default.room_limit
    # obligation: rule-success.CreateRoomFromInvitation
    # obligation: rule-failure.CreateRoomFromInvitation.2
    # obligation: rule-failure.CreateRoomFromInvitation.3
    # obligation: rule-entity-creation.CreateRoomFromInvitation.1
    # obligation: surface-actor.InvitationVisitor
    # obligation: surface-provides.InvitationVisitor
    with client_for(server.url) as admin, client_for(server.url) as visitor:
        admin_sign_in(admin, server.password)
        invitation_id, token = issue(admin)
        path = f"/api/v1/invitations/{token}"
        for _ in range(2):
            check = visitor.get(path)
            assert check.status_code == 200 and check.json() == {}
            assert "set-cookie" not in check.headers
        body = {"name": "  Secret  ", "password": "secret-pw"}
        for invalid in ({**body, "name": "ø" * 101}, {**body, "password": "abc"}):
            assert_error(
                visitor.post(f"{path}/rooms", json=invalid), 422, "invalid_request"
            )
        with storage(server) as db:
            db.execute(
                "CREATE TRIGGER fail_room_create BEFORE INSERT ON rooms BEGIN SELECT RAISE(ABORT, 'injected room failure'); END"
            )
        failure = visitor.post(f"{path}/rooms", json=body)
        assert_error(failure, 503, "unavailable")
        assert server.query("SELECT rooms_created FROM room_invitations") == [(0,)]
        with storage(server) as db:
            db.execute("DROP TRIGGER fail_room_create")

        def submit(browser: httpx.Client) -> httpx.Response:
            return browser.post(f"{path}/rooms", json=body)

        first = [submit(visitor) for _ in range(4)]
        start = Barrier(2, timeout=5)

        def last_use() -> httpx.Response:
            with client_for(server.url) as browser:
                start.wait()
                return submit(browser)

        with ThreadPoolExecutor(max_workers=2) as pool:
            races = [pool.submit(last_use) for _ in range(2)]
            final = sorted(
                (race.result() for race in races), key=lambda r: r.status_code
            )
        last, refused = final
        assert_error(refused, 404, "invitation_unavailable")
        slugs = set()
        for ok in [*first, last]:
            assert ok.status_code == 200, ok.text
            assert "set-cookie" not in ok.headers
            room = ok.json()["room"]
            assert set(room) == {"slug", "name"} and room["name"] == "Secret"
            assert re.fullmatch(r"[a-zA-Z0-9_-]{24}", room["slug"])
            slugs.add(room["slug"])
        assert len(slugs) == 5
        assert server.query("SELECT DISTINCT authorization_version FROM rooms") == [
            (1,)
        ]
        assert server.query("SELECT rooms_created FROM room_invitations") == [(5,)]
        assert server.query("SELECT COUNT(*) FROM rooms") == [(6,)]
        assert server.query("SELECT * FROM room_access_tokens") == []
        slug = first[0].json()["room"]["slug"]
        assert_error(visitor.get(session_path(slug)), 401, "not_authenticated")
        assert_error(
            visitor.get(session_path(server.room_slug)), 401, "not_authenticated"
        )
        assert sign_in(visitor, slug, "secret-pw").status_code == 200
        assert admin.delete(f"{ROOMS}/{last.json()['room']['slug']}").status_code == 204
        unavailable = visitor.get(path)
        assert_error(unavailable, 404, "invitation_unavailable")
        assert unavailable.json() == refused.json()
        [history] = admin.get(INVITATIONS).json()["invitations"]
        assert history["status"] == "inactive"
        assert history["id"] == invitation_id
        assert admin.post(f"{INVITATIONS}/{invitation_id}/revoke", json={}).json() == {}
        [history] = admin.get(INVITATIONS).json()["invitations"]
        assert history["status"] == "revoked"
        assert visitor.get(session_path(slug)).status_code == 200
        assert server.query("SELECT rooms_created FROM room_invitations") == [(5,)]
