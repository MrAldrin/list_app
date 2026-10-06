"""Admin in the JSON API: sign-in, room overview, create room, password reset.

The rules are in docs/api.md ("Admin"). The admin session
cookie is tested in `test_api_admin_session.py`.
"""

from unittest.mock import patch

import pytest
from api_helpers import (
    APP_PASSWORD,
    HTTPS,
    admin,
    assert_error,
    browser,
    client_for,
    home,
    sign_in,
)
from starlette.testclient import TestClient

import database_crud as crud
from admin_access import admin_password_matches
from database_setup import db


def password_hash(room_id: int) -> str:
    return db.execute(
        "SELECT password_hash FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]


def reset(client: TestClient, slug: str, new_password: str = "reset-pw"):
    return client.post(
        f"/api/v1/admin/rooms/{slug}/password", json={"new_password": new_password}
    )


def create(client: TestClient, name: str = "Cabin", password: str = "cabin-pw"):
    return client.post("/api/v1/admin/rooms", json={"name": name, "password": password})


# The shared password check


def test_admin_password_matches_only_app_password():
    assert admin_password_matches(APP_PASSWORD)
    assert not admin_password_matches("")
    assert not admin_password_matches(APP_PASSWORD + " ")
    assert not admin_password_matches(APP_PASSWORD.upper())
    assert not admin_password_matches("\ud800")  # Odd strings fail, never raise.


# Sign-in


def test_sign_in_sets_the_admin_cookie_and_who_am_i(admin_app):
    client = browser(admin_app)
    assert_error(client.get("/api/v1/admin/session"), 401, "admin_required")

    response = sign_in(client)

    assert response.status_code == 200
    assert response.json() == {}
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/v1/admin/session").status_code == 200
    # Only the admin cookie: no room cookie, no token in the body.
    assert set(client.cookies.keys()) == {"__Host-listapp-admin"}


def test_wrong_password_is_refused_and_signs_nobody_in(admin_app):
    client = browser(admin_app)
    for wrong in ("wrong", "", APP_PASSWORD + "x", " " + APP_PASSWORD):
        response = sign_in(client, wrong)
        assert_error(response, 401, "invalid_password")
        assert response.json()["error"]["message"] == "Wrong password"
    assert_error(client.get("/api/v1/admin/session"), 401, "admin_required")
    assert_error(client.get("/api/v1/admin/rooms"), 401, "admin_required")


def test_wrong_password_keeps_an_admin_session(admin_app):
    client = admin(admin_app)
    assert_error(sign_in(client, "wrong"), 401, "invalid_password")
    assert client.get("/api/v1/admin/session").status_code == 200


def test_room_password_is_not_the_admin_password(admin_app):
    client = browser(admin_app)
    assert_error(sign_in(client, "pw"), 401, "invalid_password")


@pytest.mark.parametrize(
    "body",
    [{}, {"password": 1}, {"password": None}, {"password": "x" * 1025}, {"x": "y"}],
)
def test_bad_sign_in_bodies_are_422(admin_app, body):
    client = browser(admin_app)
    assert_error(
        client.post("/api/v1/admin/session", json=body), 422, "invalid_request"
    )
    assert_error(client.get("/api/v1/admin/session"), 401, "admin_required")


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": HTTPS, "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_origin_admin_writes_are_rejected(admin_app, headers):
    client = browser(admin_app, origin=None)
    response = client.post(
        "/api/v1/admin/session", json={"password": APP_PASSWORD}, headers=headers
    )
    assert_error(response, 403, "forbidden_origin")
    assert_error(client.get("/api/v1/admin/session"), 401, "admin_required")

    signed_in = admin(admin_app)
    room_id, slug = home()
    before = password_hash(room_id)
    assert_error(
        signed_in.post(
            f"/api/v1/admin/rooms/{slug}/password",
            json={"new_password": "evil"},
            headers=headers,
        ),
        403,
        "forbidden_origin",
    )
    assert_error(
        signed_in.post(
            "/api/v1/admin/rooms",
            json={"name": "Evil", "password": "x"},
            headers=headers,
        ),
        403,
        "forbidden_origin",
    )
    assert_error(
        signed_in.delete("/api/v1/admin/session", headers=headers),
        403,
        "forbidden_origin",
    )
    assert password_hash(room_id) == before
    assert db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 1
    assert signed_in.get("/api/v1/admin/session").status_code == 200


def test_sign_out_ends_the_admin_session(admin_app):
    client = admin(admin_app)
    other = admin(admin_app)

    response = client.delete("/api/v1/admin/session")

    assert response.status_code == 204
    assert_error(client.get("/api/v1/admin/session"), 401, "admin_required")
    assert_error(client.get("/api/v1/admin/rooms"), 401, "admin_required")
    # Another browser stays signed in; signing out twice is fine.
    assert other.get("/api/v1/admin/session").status_code == 200
    assert client.delete("/api/v1/admin/session").status_code == 204


def test_admin_session_is_per_browser(admin_app):
    admin(admin_app)
    stranger = browser(admin_app)
    assert_error(stranger.get("/api/v1/admin/rooms"), 401, "admin_required")
    assert_error(reset(stranger, home()[1]), 401, "admin_required")


# Admin never grants room access


def test_admin_has_no_room_access(admin_app):
    room_id, slug = home()
    client = admin(admin_app)
    list_uid = db.execute("SELECT uid FROM lists").fetchone()[0]

    assert_error(client.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")
    assert_error(
        client.get(f"/api/v1/rooms/{slug}/changes?since=0"), 401, "not_authenticated"
    )
    assert_error(
        client.post(
            f"/api/v1/rooms/{slug}/ops",
            json={
                "op_id": "5d1e2c7a-1f0e-4a77-9a55-0b5f3c1d2e3f",
                "type": "list.create",
                "name": "x",
            },
        ),
        401,
        "not_authenticated",
    )
    assert_error(client.get(f"/api/v1/rooms/{slug}/events"), 401, "not_authenticated")
    assert_error(
        client.get(f"/api/v1/rooms/{slug}/lists/{list_uid}/share-link"),
        401,
        "not_authenticated",
    )
    assert_error(
        client.request("DELETE", f"/api/v1/rooms/{slug}", json={"password": "x"}),
        401,
        "not_authenticated",
    )
    # `?admin=true` changes nothing either.
    assert_error(
        client.get(f"/api/v1/rooms/{slug}/changes?since=0&admin=true"),
        401,
        "not_authenticated",
    )
    assert db.execute("SELECT COUNT(*) FROM lists").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM rooms WHERE id = ?", (room_id,)).fetchone()


# Room overview


def test_rooms_lists_every_room_by_name_ignoring_case(admin_app):
    _, home_slug = home()
    _, b_slug = crud.create_room("beach", "x")
    _, a_slug = crud.create_room("Attic", "x")
    client = admin(admin_app)

    response = client.get("/api/v1/admin/rooms")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "rooms": [
            {"slug": a_slug, "name": "Attic"},
            {"slug": b_slug, "name": "beach"},
            {"slug": home_slug, "name": "Home"},
        ]
    }


def test_rooms_can_be_empty(admin_app):
    db.execute("DELETE FROM lists")
    db.execute("DELETE FROM rooms")
    db.commit()
    assert admin(admin_app).get("/api/v1/admin/rooms").json() == {"rooms": []}


def test_rooms_database_error_is_503(admin_app):
    import sqlite3

    client = admin(admin_app)
    with patch("api.admin.get_rooms", side_effect=sqlite3.OperationalError("locked")):
        assert_error(client.get("/api/v1/admin/rooms"), 503, "unavailable")


# Create a room


def test_create_room_as_admin_and_no_room_access(admin_app):
    client = admin(admin_app)

    response = create(client, "  Beach  House ", "beach-pw")

    assert response.status_code == 200
    room = response.json()["room"]
    assert room["name"] == "Beach  House"
    row = db.execute(
        "SELECT name FROM rooms WHERE slug = ?", (room["slug"],)
    ).fetchone()
    assert row == ("Beach  House",)
    assert set(client.cookies.keys()) == {"__Host-listapp-admin"}
    assert_error(
        client.get(f"/api/v1/rooms/{room['slug']}/session"), 401, "not_authenticated"
    )
    # The password opens it.
    assert client_for(room["slug"], "beach-pw").get(
        f"/api/v1/rooms/{room['slug']}/session"
    ).json() == {"room": room}


@pytest.mark.parametrize(
    ("name", "password", "message"),
    [
        ("  ", "pw", "Room name cannot be empty"),
        ("Cabin", "", "Password cannot be empty"),
        ("Cabin", "x" * 73, "The password cannot be longer than 72 bytes"),
    ],
)
def test_create_room_refuses_bad_values(admin_app, name, password, message):
    client = admin(admin_app)
    response = create(client, name, password)
    assert_error(response, 422, "invalid_request")
    assert response.json()["error"]["message"] == message
    assert db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 1


def test_create_room_keeps_password_rules(admin_app):
    # Only an empty password is refused; spaces are a password.
    client = admin(admin_app)
    slug = create(client, "Cabin", "   ").json()["room"]["slug"]
    assert client_for(slug, "   ")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "x"},
        {"name": 1, "password": "x"},
        {"name": "x", "password": "y", "z": 1},
    ],
)
def test_create_room_bad_bodies_are_422(admin_app, body):
    client = admin(admin_app)
    assert_error(client.post("/api/v1/admin/rooms", json=body), 422, "invalid_request")
    assert db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 1


def test_create_room_needs_admin(admin_app):
    client = browser(admin_app)
    assert_error(create(client), 401, "admin_required")
    assert db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 1


# Password reset


def test_reset_password_revokes_every_token_and_wakes_streams(admin_app):
    room_id, slug = home()
    member = client_for(slug)
    client = admin(admin_app)

    with patch("api.admin.wake_streams") as wake:
        response = reset(client, slug, "  reset pw ")

    assert response.status_code == 200
    assert response.json() == {}
    wake.assert_called_once_with(room_id)
    assert_error(member.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")
    assert db.execute(
        "SELECT COUNT(*) FROM room_access_tokens WHERE room_id = ?", (room_id,)
    ).fetchone() == (0,)
    # Saved as typed, as typed before.
    assert crud.verify_room(slug, "  reset pw ") == room_id
    assert crud.verify_room(slug, "pw") is None
    assert crud.verify_room(slug, "reset pw") is None
    # Admin still has no room access.
    assert_error(client.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")


def test_reset_password_changes_only_that_room(admin_app):
    _, slug = home()
    other_id, other_slug = crud.create_room("Cabin", "cabin-pw")
    other_hash = password_hash(other_id)
    other_member = client_for(other_slug, "cabin-pw")

    assert reset(admin(admin_app), slug).status_code == 200

    assert password_hash(other_id) == other_hash
    assert other_member.get(f"/api/v1/rooms/{other_slug}/session").status_code == 200


@pytest.mark.parametrize(
    ("new_password", "message"),
    [
        ("", "New password cannot be empty"),
        ("   ", "New password cannot be empty"),
        ("x" * 73, "The password cannot be longer than 72 bytes"),
        ("\N{EURO SIGN}" * 25, "The password cannot be longer than 72 bytes"),
    ],
)
def test_reset_password_refuses_bad_passwords(admin_app, new_password, message):
    room_id, slug = home()
    before = password_hash(room_id)
    member = client_for(slug)

    response = reset(admin(admin_app), slug, new_password)

    assert_error(response, 422, "invalid_request")
    assert response.json()["error"]["message"] == message
    assert password_hash(room_id) == before
    assert member.get(f"/api/v1/rooms/{slug}/session").status_code == 200


def test_reset_password_of_a_gone_room_changes_nothing(admin_app):
    room_id, slug = home()
    crud.delete_room(room_id)
    client = admin(admin_app)

    with patch("api.admin.wake_streams") as wake:
        response = reset(client, slug)

    assert_error(response, 404, "room_unavailable")
    assert (
        response.json()["error"]["message"]
        == "Room changed or no longer exists; refresh and try again"
    )
    wake.assert_not_called()
    assert db.execute("SELECT COUNT(*) FROM rooms").fetchone() == (0,)


@pytest.mark.parametrize(
    "body", [{}, {"new_password": 1}, {"password": "x"}, {"new_password": "x" * 1025}]
)
def test_reset_password_bad_bodies_are_422(admin_app, body):
    room_id, slug = home()
    before = password_hash(room_id)
    client = admin(admin_app)
    response = client.post(f"/api/v1/admin/rooms/{slug}/password", json=body)
    assert_error(response, 422, "invalid_request")
    assert password_hash(room_id) == before


def test_reset_password_needs_admin_before_anything_else(admin_app):
    room_id, slug = home()
    before = password_hash(room_id)
    client = browser(admin_app)
    # Unknown room, bad body and good request all look the same without admin.
    assert_error(reset(client, slug), 401, "admin_required")
    assert_error(reset(client, "no-such-room"), 401, "admin_required")
    assert_error(
        client.post(f"/api/v1/admin/rooms/{slug}/password", json={}),
        401,
        "admin_required",
    )
    assert password_hash(room_id) == before
