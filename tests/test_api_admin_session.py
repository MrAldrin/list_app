"""The admin session cookie (decision 144): flags, forged and old cookies,
sign-out, same-origin writes, and that no admin endpoint works without it.
"""

import pytest
from api_helpers import APP_PASSWORD, HTTPS, admin, assert_error, browser, home, sign_in
from starlette.testclient import TestClient

import admin_access
from admin_access import admin_token_valid, issue_admin_token
from api.admin import ADMIN_COOKIE, PLAIN_ADMIN_COOKIE
from database_setup import db

HTTP = "http://testserver"

ADMIN_ENDPOINTS = [
    ("GET", "/api/v1/admin/rooms", None),
    ("POST", "/api/v1/admin/rooms", {"name": "X", "password": "y"}),
    ("POST", "/api/v1/admin/rooms/{slug}/password", {"new_password": "z"}),
    ("GET", "/api/v1/admin/invitations", None),
    ("POST", "/api/v1/admin/invitations", {}),
    ("POST", "/api/v1/admin/invitations/1/revoke", {}),
    ("GET", "/api/v1/admin/session", None),
]


def plain_browser(admin_app) -> TestClient:
    return TestClient(
        admin_app,
        base_url=HTTP,
        headers={"Origin": HTTP},
        raise_server_exceptions=False,
    )


def set_cookie_header(response) -> str:
    return response.headers["set-cookie"]


def flags(header: str) -> set[str]:
    return {part.strip().lower() for part in header.split(";")[1:]}


def with_cookie(admin_app, value: str, name: str = ADMIN_COOKIE) -> TestClient:
    client = browser(admin_app)
    client.cookies.set(name, value, domain="testserver.local")
    return client


# The cookie flags


def test_https_sign_in_sets_a_host_prefixed_secure_cookie(admin_app):
    response = sign_in(browser(admin_app))

    header = set_cookie_header(response)
    assert header.startswith(f"{ADMIN_COOKIE}=")
    assert ADMIN_COOKIE == "__Host-listapp-admin"
    assert {"secure", "httponly", "path=/", "samesite=lax"} <= flags(header)
    assert not any(flag.startswith("domain") for flag in flags(header))
    assert any(flag.startswith("max-age=") for flag in flags(header))
    # The token is only in the cookie, never in the body.
    assert response.json() == {}


def test_plain_http_cookie_has_no_prefix_and_no_secure_flag(admin_app):
    client = plain_browser(admin_app)

    response = sign_in(client)

    header = set_cookie_header(response)
    assert header.startswith(f"{PLAIN_ADMIN_COOKIE}=")
    assert "__Host-" not in header
    assert {"httponly", "path=/", "samesite=lax"} <= flags(header)
    assert "secure" not in flags(header)
    assert client.get("/api/v1/admin/session").status_code == 200
    assert client.get("/api/v1/admin/rooms").status_code == 200


def test_https_cookie_is_not_accepted_on_plain_http_and_back(admin_app):
    token = issue_admin_token()
    plain = plain_browser(admin_app)
    plain.cookies.set(ADMIN_COOKIE, token)
    assert_error(plain.get("/api/v1/admin/session"), 401, "admin_required")
    assert_error(
        with_cookie(admin_app, token, PLAIN_ADMIN_COOKIE).get("/api/v1/admin/session"),
        401,
        "admin_required",
    )


def test_each_sign_in_gets_a_new_token(admin_app):
    first = sign_in(browser(admin_app)).cookies[ADMIN_COOKIE]
    second = sign_in(browser(admin_app)).cookies[ADMIN_COOKIE]
    assert first != second
    assert admin_token_valid(first)
    assert admin_token_valid(second)


# Wrong password and bad cookies


def test_wrong_password_sets_no_cookie(admin_app):
    client = browser(admin_app)
    response = sign_in(client, "wrong")
    assert_error(response, 401, "invalid_password")
    assert "set-cookie" not in response.headers
    assert len(client.cookies) == 0


def test_no_admin_endpoint_works_without_the_cookie(admin_app):
    slug = home()[1]
    client = browser(admin_app)
    rooms_before = db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    for method, path, body in ADMIN_ENDPOINTS:
        response = client.request(method, path.format(slug=slug), json=body)
        assert_error(response, 401, "admin_required")
    assert db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == rooms_before


def test_a_session_cookie_of_another_name_is_not_admin(admin_app):
    client = browser(admin_app)
    # An old session cookie, and a room cookie, never make an admin.
    client.cookies.set("session", "authenticated", domain="testserver.local")
    client.cookies.set("__Host-listapp-room-x", "1", domain="testserver.local")
    assert_error(client.get("/api/v1/admin/rooms"), 401, "admin_required")


def tamper(case: str) -> str:
    version, expires, nonce, signature = issue_admin_token().split(".")
    flipped = signature[:-1] + ("0" if signature[-1] != "0" else "1")
    good = ".".join([version, expires, nonce, signature])
    cases = {
        "empty": "",
        "word": "x",
        "true": "true",
        "app_password": APP_PASSWORD,
        "extra_char": good + "0",
        "truncated": good[:-1],
        "no_signature": ".".join([version, expires, nonce]),
        "flipped_signature": ".".join([version, expires, nonce, flipped]),
        "later_expiry": ".".join(
            [version, str(int(expires) + 99999), nonce, signature]
        ),
        "other_nonce": ".".join([version, expires, "0" * 32, signature]),
        "other_version": ".".join(["v2", expires, nonce, signature]),
        "negative_expiry": ".".join([version, "-1", nonce, signature]),
        "extra_part": ".".join([version, expires, nonce, signature, "extra"]),
        "empty_expiry": ".".join([version, "", nonce, signature]),
        "upper_signature": ".".join([version, expires, nonce, signature.upper()]),
        "very_long": "a" * 5000,
        "unicode_digit": good.replace(version, "v\N{ARABIC-INDIC DIGIT ONE}", 1),
    }
    return cases[case]


TAMPER_CASES = [
    "empty",
    "word",
    "true",
    "app_password",
    "extra_char",
    "truncated",
    "no_signature",
    "flipped_signature",
    "later_expiry",
    "other_nonce",
    "other_version",
    "negative_expiry",
    "extra_part",
    "empty_expiry",
    "upper_signature",
    "very_long",
    "unicode_digit",
]


@pytest.mark.parametrize("case", TAMPER_CASES)
def test_forged_or_tampered_cookies_are_refused(admin_app, case):
    token = tamper(case)
    assert not admin_token_valid(token)
    if not token.isascii():
        return  # The test client cannot send it; the check above covers it.
    client = with_cookie(admin_app, token)
    assert_error(client.get("/api/v1/admin/session"), 401, "admin_required")
    assert_error(client.get("/api/v1/admin/rooms"), 401, "admin_required")
    response = client.post("/api/v1/admin/rooms", json={"name": "X", "password": "y"})
    assert_error(response, 401, "admin_required")
    assert db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 1


def test_a_token_signed_with_another_key_is_refused(admin_app, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "some-other-password")
    foreign = issue_admin_token()
    monkeypatch.setenv("APP_PASSWORD", APP_PASSWORD)
    assert not admin_token_valid(foreign)
    assert_error(
        with_cookie(admin_app, foreign).get("/api/v1/admin/rooms"),
        401,
        "admin_required",
    )


def test_a_stale_cookie_is_cleared_by_the_status_endpoint(admin_app):
    client = with_cookie(admin_app, "forged")
    response = client.get("/api/v1/admin/session")
    assert_error(response, 401, "admin_required")
    header = set_cookie_header(response)
    assert header.startswith(f'{ADMIN_COOKIE}="";') or header.startswith(
        f"{ADMIN_COOKIE}=;"
    )
    assert "max-age=0" in flags(header)
    # Without a cookie there is nothing to clear.
    assert "set-cookie" not in browser(admin_app).get("/api/v1/admin/session").headers


# Password change and expiry


def test_changed_app_password_ends_every_admin_session(admin_app, monkeypatch):
    first, second = admin(admin_app), admin(admin_app)
    assert first.get("/api/v1/admin/rooms").status_code == 200

    monkeypatch.setenv("APP_PASSWORD", "a-new-app-password")

    for client in (first, second):
        assert_error(client.get("/api/v1/admin/session"), 401, "admin_required")
        assert_error(client.get("/api/v1/admin/rooms"), 401, "admin_required")
    # The old password no longer signs in; the new one does.
    fresh = browser(admin_app)
    assert_error(sign_in(fresh, APP_PASSWORD), 401, "invalid_password")
    assert sign_in(fresh, "a-new-app-password").status_code == 200
    assert fresh.get("/api/v1/admin/rooms").status_code == 200


def test_token_expires(admin_app):
    now = 1_000_000.0
    token = issue_admin_token(now)
    lifetime = admin_access.ADMIN_SESSION_SECONDS
    assert admin_token_valid(token, now)
    assert admin_token_valid(token, now + lifetime - 1)
    assert not admin_token_valid(token, now + lifetime)
    assert not admin_token_valid(token, now + lifetime + 1)


def test_expired_cookie_is_refused(admin_app, monkeypatch):
    token = issue_admin_token(1.0)  # Long past.
    assert_error(
        with_cookie(admin_app, token).get("/api/v1/admin/rooms"),
        401,
        "admin_required",
    )


def test_cookie_lifetime_matches_the_token_lifetime(admin_app):
    header = set_cookie_header(sign_in(browser(admin_app)))
    assert f"max-age={admin_access.ADMIN_SESSION_SECONDS}" in flags(header)


# Sign-out


def test_sign_out_clears_the_cookie_with_the_same_attributes(admin_app):
    client = admin(admin_app)

    response = client.delete("/api/v1/admin/session")

    assert response.status_code == 204
    header = set_cookie_header(response)
    assert header.startswith(f'{ADMIN_COOKIE}="";') or header.startswith(
        f"{ADMIN_COOKIE}=;"
    )
    assert {"secure", "httponly", "path=/", "max-age=0"} <= flags(header)
    assert ADMIN_COOKIE not in client.cookies
    assert_error(client.get("/api/v1/admin/session"), 401, "admin_required")


def test_plain_http_sign_out_clears_the_plain_cookie(admin_app):
    client = plain_browser(admin_app)
    sign_in(client)
    response = client.delete("/api/v1/admin/session")
    assert response.status_code == 204
    assert set_cookie_header(response).startswith(f'{PLAIN_ADMIN_COOKIE}="";')
    assert "secure" not in flags(set_cookie_header(response))
    assert_error(client.get("/api/v1/admin/session"), 401, "admin_required")


def test_sign_out_is_per_browser(admin_app):
    one, two = admin(admin_app), admin(admin_app)
    assert one.delete("/api/v1/admin/session").status_code == 204
    assert two.get("/api/v1/admin/session").status_code == 200


# Same-origin writes


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": HTTPS, "Sec-Fetch-Site": "cross-site"},
        {"Origin": "http://testserver"},
    ],
)
def test_cross_origin_sign_in_sets_no_cookie(admin_app, headers):
    client = browser(admin_app, origin=None)
    response = client.post(
        "/api/v1/admin/session", json={"password": APP_PASSWORD}, headers=headers
    )
    assert_error(response, 403, "forbidden_origin")
    assert "set-cookie" not in response.headers
    assert len(client.cookies) == 0


def test_a_write_without_origin_is_rejected_even_with_the_cookie(admin_app):
    signed_in = admin(admin_app)
    cookie = signed_in.cookies[ADMIN_COOKIE]
    bare = browser(admin_app, origin=None)
    bare.cookies.set(ADMIN_COOKIE, cookie, domain="testserver.local")
    assert bare.get("/api/v1/admin/rooms").status_code == 200  # Reads are fine.
    assert_error(
        bare.post("/api/v1/admin/rooms", json={"name": "X", "password": "y"}),
        403,
        "forbidden_origin",
    )
    assert_error(bare.delete("/api/v1/admin/session"), 403, "forbidden_origin")
    assert signed_in.get("/api/v1/admin/session").status_code == 200
