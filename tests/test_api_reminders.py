"""Personal reminder enrollment and settings: the HTTP contract (docs/api-reminders.md)."""

from datetime import UTC, datetime, timedelta

import pytest
from api_helpers import assert_error, client_for, home, new_id, set_cookies
from fastapi.testclient import TestClient

import main
from database_crud import reset_room_password_by_slug
from database_setup import db
from identifiers import token_hash
from reminders import identity
from room_cookies import token_cookie_name

ENROLL = "/api/v1/rooms/{slug}/reminders/enrollment"
PREFS = "/api/v1/rooms/{slug}/reminders/preferences"
DEVICE = "/api/v1/rooms/{slug}/reminders/preferences/device"
SESSION = "/api/v1/rooms/{slug}/session"
DEVICE_COOKIE = "__Host-listapp-device"
PLAIN_DEVICE_COOKIE = "listapp-device"
START = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)


class FakeClock:
    """Replaces identity.current_time so expiry is decided by the test."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def advance(self, **delta: int) -> None:
        self.now = self.now + timedelta(**delta)


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    fake = FakeClock(START)
    monkeypatch.setattr(identity, "current_time", lambda: fake.now)
    return fake


@pytest.fixture
def phone(room, clock):
    """A signed-in client enrolled in the Home room, with its device cookie."""
    _room_id, slug, client = room
    response = client.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )
    assert response.status_code == 200, response.text
    return slug, client


def _enrollment(slug: str) -> dict:
    room_id = db.execute("SELECT id FROM rooms WHERE slug = ?", (slug,)).fetchone()[0]
    row = identity.enrollment_row_locked(
        db.execute("SELECT id FROM reminder_installations").fetchone()[0], room_id
    )
    return row


def _device_cookie_value(client: TestClient) -> str:
    return client.cookies.get(DEVICE_COOKIE)


def _room_cookie_name(slug: str) -> str:
    return token_cookie_name(slug)


def _revoke_room_cookie(client: TestClient, slug: str) -> None:
    client.cookies.delete(_room_cookie_name(slug))


# --- Reads never create or renew ---------------------------------------------


def test_get_preferences_without_device_cookie_creates_nothing(room):
    _room_id, slug, client = room

    response = client.get(PREFS.format(slug=slug))

    assert response.status_code == 200
    assert response.json() == {
        "enrollment": {"state": "not_enrolled", "revision": None}
    }
    assert "set-cookie" not in response.headers
    assert db.execute("SELECT COUNT(*) FROM reminder_installations").fetchone()[0] == 0


def test_get_device_without_device_cookie_is_null_and_creates_nothing(room):
    _room_id, slug, client = room

    response = client.get(DEVICE.format(slug=slug))

    assert response.json() == {"device": None}
    assert "set-cookie" not in response.headers
    assert db.execute("SELECT COUNT(*) FROM reminder_installations").fetchone()[0] == 0


def test_reads_do_not_renew_the_saved_grant_or_device(phone, clock):
    slug, client = phone
    before = (
        db.execute("SELECT expires_at FROM reminder_installations").fetchone()[0],
        _enrollment(slug)["expires_at"],
    )

    clock.advance(days=30)
    response = client.get(PREFS.format(slug=slug))
    client.get(DEVICE.format(slug=slug))

    assert "set-cookie" not in response.headers
    after = db.execute("SELECT expires_at FROM reminder_installations").fetchone()[0]
    assert (after, _enrollment(slug)["expires_at"]) == before


# --- Explicit enrollment ------------------------------------------------------


def test_enrollment_requires_current_room_access_and_creates_nothing(room):
    _room_id, slug, _client = room
    stranger = TestClient(
        main.app,
        base_url="https://testserver",
        headers={"Origin": "https://testserver"},
    )

    response = stranger.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )

    assert_error(response, 401, "not_authenticated")
    assert "set-cookie" not in response.headers
    assert db.execute("SELECT COUNT(*) FROM reminder_installations").fetchone()[0] == 0


def test_enrollment_creates_device_and_enrollment_with_defaults(room, clock):
    _room_id, slug, client = room

    response = client.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )

    assert response.status_code == 200
    body = response.json()["enrollment"]
    assert body["state"] == "active"
    assert body["mode"] == "daily_summary"
    assert body["summary_time"] == "09:00"
    assert body["revision"] == 1
    assert body["activated_at"] == "2026-11-04T10:00:00Z"
    installation = db.execute(
        "SELECT timezone, expires_at FROM reminder_installations"
    ).fetchone()
    assert installation == ("Europe/Oslo", "2027-11-04T10:00:00Z")
    grant = _enrollment(slug)
    assert grant["status"] == "active"
    assert grant["expires_at"] == "2027-11-04T10:00:00Z"


def test_device_cookie_has_host_only_secure_lifetime_and_no_domain(room):
    _room_id, slug, client = room

    response = client.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )

    morsel = set_cookies(response)[DEVICE_COOKIE]
    assert morsel["path"] == "/"
    assert morsel["secure"] is True
    assert morsel["httponly"] is True
    assert morsel["samesite"].lower() == "lax"
    assert morsel["max-age"] == "31536000"
    assert morsel["domain"] == ""


def test_plain_http_device_cookie_uses_plain_name_without_secure(room):
    _room_id, slug, _client = room
    http = TestClient(
        main.app,
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    )
    http.post(SESSION.format(slug=slug), json={"password": "pw"})

    response = http.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )

    morsel = set_cookies(response)[PLAIN_DEVICE_COOKIE]
    assert morsel["secure"] == ""
    assert morsel["httponly"] is True
    assert DEVICE_COOKIE not in set_cookies(response)


def test_stored_secret_is_only_a_hash_and_never_in_the_response(room):
    _room_id, slug, client = room

    response = client.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )

    secret = _device_cookie_value(client)
    assert secret and secret not in response.text
    stored = db.execute("SELECT secret_hash FROM reminder_installations").fetchone()[0]
    assert stored == token_hash(secret)
    assert (
        secret
        not in db.execute(
            "SELECT group_concat(response_json) FROM reminder_processed_ops"
        ).fetchone()[0]
    )


def test_new_device_without_timezone_is_rejected(room):
    _room_id, slug, client = room

    response = client.post(ENROLL.format(slug=slug), json={"op_id": new_id()})

    assert_error(response, 422, "invalid_request")
    assert db.execute("SELECT COUNT(*) FROM reminder_installations").fetchone()[0] == 0


def test_unknown_timezone_is_rejected_without_fallback(room):
    _room_id, slug, client = room

    response = client.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Mars/Olympus"}
    )

    assert_error(response, 422, "invalid_request")


def test_forged_device_cookie_is_not_an_installation(room):
    _room_id, slug, client = room
    client.cookies.set(DEVICE_COOKIE, "forged-secret-that-matches-nothing")

    response = client.get(PREFS.format(slug=slug))

    assert response.json()["enrollment"]["state"] == "not_enrolled"
    patch = client.patch(
        PREFS.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "mode": "quiet"},
    )
    assert_error(patch, 403, "not_enrolled")


# --- Two rooms, two devices ----------------------------------------------------


def test_one_device_enrolls_in_two_rooms_and_each_grant_is_separate(room, clock):
    _room_id, slug, client = room
    second_slug = _second_room(client)

    client.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )
    client.post(ENROLL.format(slug=second_slug), json={"op_id": new_id()})

    assert db.execute("SELECT COUNT(*) FROM reminder_installations").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM reminder_enrollments").fetchone()[0] == 2
    assert (
        client.get(PREFS.format(slug=second_slug)).json()["enrollment"]["state"]
        == "active"
    )


def test_device_cookie_alone_grants_no_room_access(phone):
    slug, client = phone
    _revoke_room_cookie(client, slug)

    response = client.get(PREFS.format(slug=slug))
    patch = client.patch(
        PREFS.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "mode": "quiet"},
    )

    assert_error(response, 401, "not_authenticated")
    assert_error(patch, 401, "not_authenticated")


def test_device_of_one_room_cannot_read_another_rooms_enrollment(phone):
    _slug, client = phone
    other_slug = _second_room(client)

    # The second room has its own grant; this device is not enrolled in it.
    response = client.get(PREFS.format(slug=other_slug))

    assert response.json()["enrollment"]["state"] == "not_enrolled"


def test_two_installations_are_isolated(room, clock):
    _room_id, slug, first = room
    second = client_for(slug)
    first.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )
    second.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )
    base = first.get(PREFS.format(slug=slug)).json()["enrollment"]["revision"]

    response = second.patch(
        PREFS.format(slug=slug),
        json={"op_id": new_id(), "base_revision": base, "mode": "quiet"},
    )

    assert response.status_code == 200
    assert db.execute("SELECT COUNT(*) FROM reminder_installations").fetchone()[0] == 2
    assert first.get(PREFS.format(slug=slug)).json()["enrollment"]["mode"] == (
        "daily_summary"
    )


# --- Idempotency and revisions --------------------------------------------------


def test_enrollment_replay_returns_stored_result_without_reapplying(room, clock):
    _room_id, slug, client = room
    op_id = new_id()
    body = {"op_id": op_id, "timezone": "Europe/Oslo", "mode": "scheduled"}
    first = client.post(ENROLL.format(slug=slug), json=body)
    assert first.status_code == 200
    revision = _enrollment(slug)["revision"]
    clock.advance(hours=5)

    replay = client.post(ENROLL.format(slug=slug), json=body)

    assert replay.status_code == 200
    assert replay.json()["enrollment"]["revision"] == revision
    assert _enrollment(slug)["revision"] == revision
    assert _enrollment(slug)["activated_at"] == "2026-11-04T10:00:00Z"


def test_reused_enrollment_op_id_with_another_body_is_409(room):
    _room_id, slug, client = room
    op_id = new_id()
    client.post(
        ENROLL.format(slug=slug),
        json={"op_id": op_id, "timezone": "Europe/Oslo", "mode": "quiet"},
    )

    response = client.post(
        ENROLL.format(slug=slug),
        json={"op_id": op_id, "timezone": "Europe/Oslo", "mode": "custom"},
    )

    assert_error(response, 409, "op_id_reused")


def test_personal_ops_never_use_the_shared_processed_ops_table(room):
    _room_id, slug, client = room
    before = db.execute("SELECT COUNT(*) FROM processed_ops").fetchone()[0]

    client.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )

    assert db.execute("SELECT COUNT(*) FROM processed_ops").fetchone()[0] == before


def test_preferences_patch_needs_matching_revision(phone):
    slug, client = phone
    first = client.patch(
        PREFS.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "mode": "quiet"},
    )
    assert first.status_code == 200
    assert first.json()["enrollment"]["revision"] == 2

    stale = client.patch(
        PREFS.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "mode": "scheduled"},
    )

    assert_error(stale, 409, "revision_conflict")
    assert client.get(PREFS.format(slug=slug)).json()["enrollment"]["mode"] == "quiet"


def test_preferences_patch_replay_is_idempotent(phone):
    slug, client = phone
    op_id = new_id()
    body = {"op_id": op_id, "base_revision": 1, "summary_time": "07:30"}
    first = client.patch(PREFS.format(slug=slug), json=body)

    replay = client.patch(PREFS.format(slug=slug), json=body)

    assert replay.json() == first.json()
    assert _enrollment(slug)["revision"] == 2


def test_device_patch_is_device_scoped_and_checks_its_own_revision(phone):
    slug, client = phone
    first = client.patch(
        DEVICE.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "daily_cap": 5},
    )
    assert first.status_code == 200
    assert first.json()["device"]["daily_cap"] == 5
    assert first.json()["device"]["revision"] == 2

    stale = client.patch(
        DEVICE.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "paused": True},
    )

    assert_error(stale, 409, "revision_conflict")


def test_device_and_enrollment_idempotency_namespaces_do_not_collide(phone):
    slug, client = phone
    shared_op = new_id()
    client.patch(
        PREFS.format(slug=slug),
        json={"op_id": shared_op, "base_revision": 1, "mode": "quiet"},
    )

    response = client.patch(
        DEVICE.format(slug=slug),
        json={"op_id": shared_op, "base_revision": 1, "daily_cap": 3},
    )

    assert response.status_code == 200
    assert response.json()["device"]["daily_cap"] == 3


def test_device_patch_absent_and_null_are_different_and_null_clears_quiet(phone):
    slug, client = phone
    client.patch(
        DEVICE.format(slug=slug),
        json={
            "op_id": new_id(),
            "base_revision": 1,
            "quiet_hours": {"start": "23:00", "end": "07:00"},
        },
    )
    device = client.get(DEVICE.format(slug=slug)).json()["device"]
    assert device["quiet_hours"] == {"start": "23:00", "end": "07:00"}

    cleared = client.patch(
        DEVICE.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 2, "quiet_hours": None},
    )

    assert cleared.json()["device"]["quiet_hours"] is None


@pytest.mark.parametrize(
    "field, value",
    [
        ("daily_cap", 0),
        ("daily_cap", 51),
        ("spacing_minutes", 61),
        ("content_privacy", "lock-screen"),
        ("overdue_repeat_days", 31),
        ("all_day_time", "25:00"),
        ("timezone", "Mars/Olympus"),
        ("paused", "yes"),
        ("daily_cap", None),
    ],
)
def test_device_patch_rejects_invalid_values(phone, field, value):
    slug, client = phone

    response = client.patch(
        DEVICE.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, field: value},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_enrollment_rejects_unknown_fields(phone):
    slug, client = phone

    response = client.patch(
        PREFS.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "installation_id": 9},
    )

    assert_error(response, 422, "invalid_request")


# --- Request safety (CSRF, JSON, size) ---------------------------------------------


def test_enrollment_rejects_cross_origin_and_non_json(room):
    _room_id, slug, client = room

    cross = client.post(
        ENROLL.format(slug=slug),
        json={"op_id": new_id(), "timezone": "Europe/Oslo"},
        headers={"Origin": "https://evil.example"},
    )
    text = client.post(
        ENROLL.format(slug=slug),
        content=b"op_id=1",
        headers={"Content-Type": "text/plain"},
    )

    assert_error(cross, 403, "forbidden_origin")
    assert_error(text, 415, "invalid_request")
    assert db.execute("SELECT COUNT(*) FROM reminder_installations").fetchone()[0] == 0


def test_oversized_enrollment_body_is_413(room):
    _room_id, slug, client = room

    response = client.post(
        ENROLL.format(slug=slug),
        content=b"{" + b'"x":"' + b"a" * (65 * 1024) + b'"}',
        headers={"Content-Type": "application/json"},
    )

    assert_error(response, 413, "invalid_request")


def test_enrollment_rejects_non_object_json(room):
    _room_id, slug, client = room

    response = client.post(
        ENROLL.format(slug=slug),
        content=b"[1,2]",
        headers={"Content-Type": "application/json"},
    )

    assert_error(response, 422, "invalid_request")


# --- Shared surfaces stay unchanged -------------------------------------------------


def test_private_writes_do_not_bump_change_seq_or_wake_streams(phone, notified):
    slug, client = phone
    room_id = db.execute("SELECT id FROM rooms WHERE slug = ?", (slug,)).fetchone()[0]
    seq = db.execute(
        "SELECT change_seq FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]
    notified.clear()

    client.patch(
        PREFS.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "mode": "quiet"},
    )
    client.patch(
        DEVICE.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "paused": True},
    )

    assert (
        db.execute("SELECT change_seq FROM rooms WHERE id = ?", (room_id,)).fetchone()[
            0
        ]
        == seq
    )
    assert notified == []


def test_personal_settings_stay_out_of_the_shared_changes_feed(phone):
    slug, client = phone
    client.patch(
        PREFS.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "mode": "quiet"},
    )

    feed = client.get(f"/api/v1/rooms/{slug}/changes?since=0").text

    assert "quiet" not in feed
    assert "Europe/Oslo" not in feed
    assert "installation" not in feed


# --- Expiry, resume and revocation -----------------------------------------------------


def test_expired_grant_needs_resume_and_is_not_renewed_by_a_read(phone, clock):
    slug, client = phone
    db.execute("UPDATE reminder_enrollments SET expires_at = '2026-11-04T11:00:00Z'")
    db.commit()
    clock.advance(hours=2)

    response = client.get(PREFS.format(slug=slug))

    assert response.json()["enrollment"]["state"] == "needs_resume"
    assert "set-cookie" not in response.headers
    assert _enrollment(slug)["expires_at"] == "2026-11-04T11:00:00Z"


def test_expired_device_is_not_an_installation_and_reads_cannot_renew_it(phone, clock):
    slug, client = phone
    clock.advance(days=366)

    response = client.get(PREFS.format(slug=slug))
    patch = client.patch(
        PREFS.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "mode": "quiet"},
    )

    assert response.json()["enrollment"]["state"] == "not_enrolled"
    assert_error(patch, 403, "not_enrolled")
    assert "set-cookie" not in response.headers


def test_explicit_resume_renews_a_lapsed_grant_and_keeps_preferences(phone, clock):
    slug, client = phone
    client.patch(
        PREFS.format(slug=slug),
        json={
            "op_id": new_id(),
            "base_revision": 1,
            "mode": "scheduled",
            "summary_time": "07:30",
        },
    )
    db.execute("UPDATE reminder_enrollments SET expires_at = '2026-11-04T10:30:00Z'")
    db.commit()
    clock.advance(hours=1)
    assert client.get(PREFS.format(slug=slug)).json()["enrollment"]["state"] == (
        "needs_resume"
    )

    resume = client.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "base_revision": 2}
    )

    assert resume.status_code == 200
    body = resume.json()["enrollment"]
    assert body["state"] == "active"
    assert body["mode"] == "scheduled"
    assert body["summary_time"] == "07:30"
    assert body["activated_at"] == "2026-11-04T11:00:00Z"


def test_sign_out_disables_the_grant_without_any_page_and_resume_keeps_prefs(
    phone, clock
):
    slug, client = phone
    client.patch(
        PREFS.format(slug=slug),
        json={"op_id": new_id(), "base_revision": 1, "mode": "quiet"},
    )

    signed_out = client.delete(SESSION.format(slug=slug))
    assert signed_out.status_code == 204
    assert _enrollment(slug)["status"] == "revoked"
    # Signing in again does not silently resume the old enrollment.
    client.post(SESSION.format(slug=slug), json={"password": "pw"})
    assert client.get(PREFS.format(slug=slug)).json()["enrollment"]["state"] == (
        "needs_resume"
    )

    resume = client.post(
        ENROLL.format(slug=slug),
        json={"op_id": new_id(), "base_revision": _enrollment(slug)["revision"]},
    )

    assert resume.json()["enrollment"]["state"] == "active"
    assert resume.json()["enrollment"]["mode"] == "quiet"


def test_password_change_disables_every_enrollment_of_the_room(phone):
    slug, client = phone
    before_seq = _enrollment(slug)["revision"]

    client.post(
        f"/api/v1/rooms/{slug}/password",
        json={"current_password": "pw", "new_password": "a-new-password"},
    )

    assert _enrollment(slug)["status"] == "revoked"
    assert _enrollment(slug)["revision"] == before_seq + 1


def test_admin_password_reset_disables_enrollments_with_no_open_page(phone):
    slug, _client = phone

    reset_room_password_by_slug(slug, "another-password")

    assert _enrollment(slug)["status"] == "revoked"


def test_room_deletion_removes_its_enrollments_only(phone):
    slug, client = phone
    other = _second_room(client)
    client.post(ENROLL.format(slug=other), json={"op_id": new_id()})

    client.request(
        "DELETE",
        f"/api/v1/rooms/{slug}",
        json={"password": "pw"},
    )

    assert db.execute("SELECT COUNT(*) FROM reminder_enrollments").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM reminder_installations").fetchone()[0] == 1


def test_saved_grant_state_is_pure_validation_and_writes_nothing(phone):
    slug, _client = phone
    room_id = db.execute("SELECT id FROM rooms WHERE slug = ?", (slug,)).fetchone()[0]
    installation_id = db.execute("SELECT id FROM reminder_installations").fetchone()[0]
    db.execute("UPDATE room_access_tokens SET revoked_at = CURRENT_TIMESTAMP")
    db.commit()
    before = db.execute("SELECT * FROM reminder_enrollments").fetchall()

    state = identity.saved_grant_state_locked(installation_id, room_id)

    assert state == "needs_resume"
    assert db.execute("SELECT * FROM reminder_enrollments").fetchall() == before


def test_sign_in_on_another_browser_does_not_resume_this_device(room, clock):
    _room_id, slug, client = room
    client.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )
    other = client_for(slug)
    assert other.get(PREFS.format(slug=slug)).json()["enrollment"]["state"] == (
        "not_enrolled"
    )


def _second_room(client: TestClient) -> str:
    """Create a second room with the same test password and sign in the client to it."""
    from password_hashing import hash_password

    slug = f"second-{new_id()[:6]}"
    db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES ('Second', ?, ?)",
        (slug, hash_password("pw")),
    )
    db.commit()
    response = client.post(SESSION.format(slug=slug), json={"password": "pw"})
    assert response.status_code == 200
    return slug


def test_home_fixture_is_present_for_helpers():
    room_id, slug = home()
    assert room_id and slug
