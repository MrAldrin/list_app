"""The room password minimum (4 characters) on every path that sets a password.

Sign-in does not apply the rule, so rooms with older, shorter passwords still open.
"""

import pytest
from api_helpers import (
    HTTPS,
    admin,
    assert_error,
    client_for,
    home,
    verify_room,
)
from starlette.testclient import TestClient

import main
from database_crud import check_new_room_password
from database_setup import db


@pytest.mark.parametrize("password", ["abcd", "a b c", "éééé", "  ab  "])
def test_four_or_more_characters_are_accepted(password):
    check_new_room_password(password)


@pytest.mark.parametrize("password", ["abc", "ab", "a", "éé", " ab"])
def test_fewer_than_four_characters_are_refused(password):
    with pytest.raises(ValueError, match="Password must be at least 4 characters"):
        check_new_room_password(password)


def test_blank_is_refused_with_its_own_message():
    with pytest.raises(ValueError, match="Password cannot be empty"):
        check_new_room_password("   ")


def test_admin_cannot_create_a_room_with_a_short_password(admin_app):
    client = admin(admin_app)
    response = client.post(
        "/api/v1/admin/rooms", json={"name": "Cabin", "password": "abc"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        "Password must be at least 4 characters"
    )
    assert db.execute("SELECT COUNT(*) FROM rooms WHERE name = 'Cabin'").fetchone() == (
        0,
    )


def test_admin_can_create_a_room_with_four_characters(admin_app):
    client = admin(admin_app)
    response = client.post(
        "/api/v1/admin/rooms", json={"name": "Cabin", "password": "abcd"}
    )

    assert response.status_code == 200


def test_admin_reset_refuses_a_short_password_and_keeps_the_old_one(admin_app):
    room_id, slug = home()
    client = admin(admin_app)

    response = client.post(
        f"/api/v1/admin/rooms/{slug}/password", json={"new_password": "abc"}
    )

    assert response.status_code == 422
    assert verify_room(slug, "pw") == room_id


def test_password_change_refuses_a_short_password_and_keeps_the_old_one():
    room_id, slug = home()
    member = client_for(slug)

    response = member.post(
        f"/api/v1/rooms/{slug}/password",
        json={"current_password": "pw", "new_password": "abc"},
    )

    assert response.status_code == 422
    assert verify_room(slug, "pw") == room_id


def test_invitation_room_refuses_a_short_password(admin_app):
    client = admin(admin_app)
    issued = client.post("/api/v1/admin/invitations", json={})
    assert issued.status_code == 200
    token = issued.json()["token"]
    anonymous = TestClient(
        main.app,
        base_url=HTTPS,
        headers={"Origin": HTTPS},
        raise_server_exceptions=False,
    )

    response = anonymous.post(
        f"/api/v1/invitations/{token}/rooms",
        json={"name": "Cabin", "password": "abc"},
    )

    assert_error(response, 422, "invalid_request")
    assert response.json()["error"]["message"] == (
        "Password must be at least 4 characters"
    )
    assert db.execute("SELECT COUNT(*) FROM rooms WHERE name = 'Cabin'").fetchone() == (
        0,
    )


def test_existing_short_password_still_signs_in():
    room_id, slug = home()

    # client_for asserts a 200 answer: the older 2-character password still opens the room.
    member = client_for(slug, "pw")

    assert member.get(f"/api/v1/rooms/{slug}/session").status_code == 200
    assert verify_room(slug, "pw") == room_id


def test_changing_from_a_short_password_to_a_valid_one_works():
    room_id, slug = home()
    member = client_for(slug, "pw")

    response = member.post(
        f"/api/v1/rooms/{slug}/password",
        json={"current_password": "pw", "new_password": "longer-pass"},
    )

    assert response.status_code == 200
    assert verify_room(slug, "longer-pass") == room_id
