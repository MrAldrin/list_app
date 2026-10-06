"""Creation invitations in the JSON API: admins issue, list and revoke them;
anyone with a link can create a room (docs/api.md, "Creation invitations").

The rules are in `src/room_invitations.py`, docs/room-invitations.md.
Times are moved by editing the stored rows, not by patching `time.time`, which
would also change the signed session cookie of the admin test app.
"""

import hashlib
import time
from unittest.mock import patch

import pytest
from api_helpers import HTTPS, admin, assert_error, browser, client_for

import room_invitations as invitations
from database_crud import get_rooms, verify_room
from database_setup import db

INVALID = "This invitation is invalid or no longer active."


def issue(client):
    return client.post("/api/v1/admin/invitations", json={})


def listing(client) -> list[dict]:
    response = client.get("/api/v1/admin/invitations")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["invitations"]


def revoke(client, invitation_id):
    return client.post(f"/api/v1/admin/invitations/{invitation_id}/revoke", json={})


def create_room(client, token: str, name: str = "Cabin", password: str = "cabin-pw"):
    return client.post(
        f"/api/v1/invitations/{token}/rooms", json={"name": name, "password": password}
    )


def room_count() -> int:
    return db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]


def set_times(invitation_id: int, **columns: int) -> None:
    for column, value in columns.items():
        db.execute(
            f"UPDATE room_invitations SET {column} = ? WHERE id = ?",
            (value, invitation_id),
        )
    db.commit()


# Admin: issue


def test_issue_returns_the_token_once_and_stores_only_its_hash(admin_app):
    client = admin(admin_app)
    before = int(time.time())

    response = issue(client)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    token = data["token"]
    invitation = data["invitation"]
    assert len(token) >= 43
    assert set(invitation) == {"id", "status", "created_at", "expires_at", "revoked_at"}
    assert invitation["status"] == "active"
    assert invitation["revoked_at"] is None
    stored = db.execute(
        "SELECT token_hash, created_at, expires_at FROM room_invitations WHERE id = ?",
        (invitation["id"],),
    ).fetchone()
    assert stored[0] == hashlib.sha256(token.encode()).hexdigest()
    assert before <= stored[1] <= int(time.time())
    assert stored[2] - stored[1] == 7 * 24 * 60 * 60
    assert invitations.invitation_is_active(token)
    # The listing never shows the token again.
    assert listing(client) == [invitation]
    assert token not in client.get("/api/v1/admin/invitations").text
    # No room cookie, no room.
    assert set(client.cookies.keys()) == {"__Host-listapp-admin"}
    assert room_count() == 1


def test_times_are_utc_iso_strings(admin_app):
    client = admin(admin_app)
    invitation_id = issue(client).json()["invitation"]["id"]
    in_2100 = 4_102_444_800  # 2100-01-01 00:00 UTC
    set_times(invitation_id, created_at=in_2100, expires_at=in_2100 + 7 * 86_400)
    set_times(invitation_id, revoked_at=in_2100 + 90)

    [row] = listing(client)

    assert row["created_at"] == "2100-01-01T00:00:00Z"
    assert row["expires_at"] == "2100-01-08T00:00:00Z"
    assert row["revoked_at"] == "2100-01-01T00:01:30Z"


@pytest.mark.parametrize("body", [{"x": 1}, {"days": 7}])
def test_issue_takes_an_empty_body(admin_app, body):
    client = admin(admin_app)
    response = client.post("/api/v1/admin/invitations", json=body)
    assert_error(response, 422, "invalid_request")
    assert db.execute("SELECT COUNT(*) FROM room_invitations").fetchone() == (0,)


# Admin: listing


def test_listing_shows_status_newest_first(admin_app):
    client = admin(admin_app)
    first = issue(client).json()["invitation"]["id"]
    second = issue(client).json()["invitation"]["id"]
    third = issue(client).json()["invitation"]["id"]
    now = int(time.time())
    set_times(first, expires_at=now - 1)
    assert revoke(client, second).status_code == 200

    rows = listing(client)

    assert [row["id"] for row in rows] == [third, second, first]
    assert [row["status"] for row in rows] == ["active", "revoked", "expired"]
    assert rows[1]["revoked_at"] is not None
    assert rows[2]["revoked_at"] is None


def test_revoked_wins_over_expired(admin_app):
    client = admin(admin_app)
    invitation_id = issue(client).json()["invitation"]["id"]
    now = int(time.time())
    set_times(invitation_id, expires_at=now - 10, revoked_at=now - 5)
    assert [row["status"] for row in listing(client)] == ["revoked"]


def test_listing_prunes_records_inactive_for_seven_days(admin_app):
    client = admin(admin_app)
    old = issue(client).json()["invitation"]["id"]
    kept = issue(client).json()["invitation"]["id"]
    now = int(time.time())
    retention = invitations.INVITATION_RETENTION
    set_times(old, expires_at=now - retention - 1)
    set_times(kept, expires_at=now - retention + 60)

    assert [row["id"] for row in listing(client)] == [kept]
    assert db.execute("SELECT id FROM room_invitations ORDER BY id").fetchall() == [
        (kept,)
    ]


def test_listing_can_be_empty(admin_app):
    assert listing(admin(admin_app)) == []


# Admin: revoke


def test_revoke_stops_creation_but_keeps_rooms(admin_app):
    client = admin(admin_app)
    data = issue(client).json()
    token = data["token"]
    public = client_for()
    slug = create_room(public, token).json()["room"]["slug"]

    response = revoke(client, data["invitation"]["id"])

    assert response.status_code == 200
    assert response.json() == {}
    assert not invitations.invitation_is_active(token)
    assert_error(create_room(public, token, "Denied"), 404, "invitation_unavailable")
    assert verify_room(slug, "cabin-pw")
    # A second revoke changes nothing and keeps the first time.
    revoked_at = listing(client)[0]["revoked_at"]
    assert revoke(client, data["invitation"]["id"]).status_code == 200
    assert listing(client)[0]["revoked_at"] == revoked_at


def test_revoke_of_an_unknown_invitation_changes_nothing(admin_app):
    client = admin(admin_app)
    data = issue(client).json()
    assert revoke(client, data["invitation"]["id"] + 1).status_code == 200
    assert invitations.invitation_is_active(data["token"])


def test_revoke_changes_only_that_invitation(admin_app):
    client = admin(admin_app)
    first = issue(client).json()
    second = issue(client).json()
    assert revoke(client, first["invitation"]["id"]).status_code == 200
    assert not invitations.invitation_is_active(first["token"])
    assert invitations.invitation_is_active(second["token"])


@pytest.mark.parametrize("invitation_id", ["0", "-1", "x", "1.5", str(2**63)])
def test_revoke_bad_ids_are_422(admin_app, invitation_id):
    client = admin(admin_app)
    assert_error(revoke(client, invitation_id), 422, "invalid_request")


@pytest.mark.parametrize("body", [{"x": 1}, {"id": 1}])
def test_revoke_takes_an_empty_body(admin_app, body):
    client = admin(admin_app)
    data = issue(client).json()
    response = client.post(
        f"/api/v1/admin/invitations/{data['invitation']['id']}/revoke", json=body
    )
    assert_error(response, 422, "invalid_request")
    assert invitations.invitation_is_active(data["token"])


# Admin: access rules


def test_admin_endpoints_need_admin_before_anything_else(admin_app):
    invitation_id, token = invitations.create_invitation()
    client = browser(admin_app)

    assert_error(issue(client), 401, "admin_required")
    assert_error(
        client.post("/api/v1/admin/invitations", json={"x": 1}), 401, "admin_required"
    )
    assert_error(client.get("/api/v1/admin/invitations"), 401, "admin_required")
    assert_error(revoke(client, invitation_id), 401, "admin_required")
    assert_error(revoke(client, "x"), 401, "admin_required")
    assert db.execute("SELECT COUNT(*) FROM room_invitations").fetchone() == (1,)
    assert invitations.invitation_is_active(token)


def test_signing_out_ends_invitation_management(admin_app):
    client = admin(admin_app)
    invitation_id = issue(client).json()["invitation"]["id"]
    assert client.delete("/api/v1/admin/session").status_code == 204
    assert_error(issue(client), 401, "admin_required")
    assert_error(revoke(client, invitation_id), 401, "admin_required")
    assert_error(client.get("/api/v1/admin/invitations"), 401, "admin_required")


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": HTTPS, "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_origin_writes_are_rejected(admin_app, headers):
    client = admin(admin_app)
    invitation_id, token = invitations.create_invitation()

    assert_error(
        client.post("/api/v1/admin/invitations", json={}, headers=headers),
        403,
        "forbidden_origin",
    )
    assert_error(
        client.post(
            f"/api/v1/admin/invitations/{invitation_id}/revoke",
            json={},
            headers=headers,
        ),
        403,
        "forbidden_origin",
    )
    assert_error(
        client.post(
            f"/api/v1/invitations/{token}/rooms",
            json={"name": "Evil", "password": "x"},
            headers=headers,
        ),
        403,
        "forbidden_origin",
    )
    assert db.execute("SELECT COUNT(*) FROM room_invitations").fetchone() == (1,)
    assert invitations.invitation_is_active(token)
    assert room_count() == 1


# Public: check a link


def test_check_says_whether_a_link_can_create_a_room():
    invitation_id, token = invitations.create_invitation()
    client = client_for()

    response = client.get(f"/api/v1/invitations/{token}")
    assert response.status_code == 200
    assert response.json() == {}
    assert response.headers["cache-control"] == "no-store"

    invitations.revoke_invitation(invitation_id)
    response = client.get(f"/api/v1/invitations/{token}")
    assert_error(response, 404, "invitation_unavailable")
    assert response.json()["error"]["message"] == INVALID


@pytest.mark.parametrize("state", ["unknown", "expired", "revoked", "pruned"])
def test_unavailable_links_all_look_the_same(state):
    invitation_id, token = invitations.create_invitation()
    if state == "unknown":
        token = "wrong"
    elif state == "expired":
        set_times(invitation_id, expires_at=int(time.time()))
    elif state == "revoked":
        invitations.revoke_invitation(invitation_id)
    else:
        db.execute("DELETE FROM room_invitations")
        db.commit()
    client = client_for()

    check = client.get(f"/api/v1/invitations/{token}")
    create = create_room(client, token)

    for response in (check, create):
        assert_error(response, 404, "invitation_unavailable")
        assert response.json()["error"]["message"] == INVALID
    assert room_count() == 1


# Public: create a room


def test_create_room_from_a_link_without_signing_in():
    _, token = invitations.create_invitation()
    client = client_for()

    response = create_room(client, token, "  Beach  House ", "beach-pw")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    room = response.json()["room"]
    assert room["name"] == "Beach  House"
    assert db.execute(
        "SELECT name FROM rooms WHERE slug = ?", (room["slug"],)
    ).fetchone() == ("Beach  House",)
    # The creator signs in with the new password next.
    assert not client.cookies
    assert_error(
        client.get(f"/api/v1/rooms/{room['slug']}/session"), 401, "not_authenticated"
    )
    member = client_for(room["slug"], "beach-pw")
    assert member.get(f"/api/v1/rooms/{room['slug']}/session").json() == {"room": room}
    # Reusable until it expires.
    assert invitations.invitation_is_active(token)


def test_a_link_is_reusable_and_never_opens_other_rooms():
    _, token = invitations.create_invitation()
    client = client_for()
    first = create_room(client, token, "First", "first-pw").json()["room"]["slug"]
    second = create_room(client, token, "First", "second-pw").json()["room"]["slug"]

    assert first != second
    assert verify_room(first, "first-pw")
    assert not verify_room(second, "first-pw")
    assert len(get_rooms()) == 3
    assert_error(client.get(f"/api/v1/rooms/{first}/session"), 401, "not_authenticated")


def test_admin_sign_in_is_not_needed_and_gives_no_room_access(admin_app):
    client = admin(admin_app)
    token = issue(client).json()["token"]
    slug = create_room(client, token).json()["room"]["slug"]
    assert set(client.cookies.keys()) == {"__Host-listapp-admin"}
    assert_error(client.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated")


@pytest.mark.parametrize(
    ("name", "password"),
    [
        (" ", "pw"),
        ("x" * 101, "pw"),
        ("Room", ""),
        ("Room", " "),
        ("Room", "\N{LATIN SMALL LETTER E WITH ACUTE}" * 37),
    ],
)
def test_bad_names_and_passwords_are_422_with_clear_messages(name, password):
    _, token = invitations.create_invitation()
    client = client_for()

    response = create_room(client, token, name, password)

    assert_error(response, 422, "invalid_request")
    message = response.json()["error"]["message"]
    assert message in (
        "Room name must contain 1-100 characters.",
        "Password must be nonblank and at most 72 UTF-8 bytes.",
    )
    assert room_count() == 1
    assert invitations.invitation_is_active(token)


def test_password_is_saved_as_typed_and_100_characters_fit():
    _, token = invitations.create_invitation()
    response = create_room(client_for(), token, "x" * 100, "  spaced pw ")
    slug = response.json()["room"]["slug"]
    assert verify_room(slug, "  spaced pw ")
    assert not verify_room(slug, "spaced pw")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "x"},
        {"password": "x"},
        {"name": 1, "password": "x"},
        {"name": "x", "password": None},
        {"name": "x", "password": "y", "confirm": "y"},
        {"name": "x", "password": "y" * 1025},
    ],
)
def test_bad_bodies_are_422(body):
    _, token = invitations.create_invitation()
    response = client_for().post(f"/api/v1/invitations/{token}/rooms", json=body)
    assert_error(response, 422, "invalid_request")
    assert room_count() == 1


def test_invitation_is_checked_again_after_hashing_the_password():
    invitation_id, token = invitations.create_invitation()
    original = invitations.bcrypt.hashpw

    def hash_and_revoke(*args):
        result = original(*args)
        invitations.revoke_invitation(invitation_id)
        return result

    with patch.object(invitations.bcrypt, "hashpw", hash_and_revoke):
        response = create_room(client_for(), token)

    assert_error(response, 404, "invitation_unavailable")
    assert room_count() == 1
    assert not db.in_transaction


def test_shared_status_rule():
    now = time.time()
    status = invitations.invitation_status
    assert status({"revoked_at": None, "expires_at": now + 60}) == "active"
    assert status({"revoked_at": None, "expires_at": now - 1}) == "expired"
    assert status({"revoked_at": 1, "expires_at": now + 60}) == "revoked"
    assert status({"revoked_at": 1, "expires_at": now - 1}) == "revoked"
