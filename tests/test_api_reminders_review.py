"""Regression tests for the milestone A review: expiry, idempotency, replay state, hooks."""

from datetime import UTC, datetime, timedelta

import pytest
from api_helpers import assert_error, client_for, new_id

from database_crud import revoke_room_access_token
from database_setup import db
from reminders import identity

ENROLL = "/api/v1/rooms/{slug}/reminders/enrollment"
PREFS = "/api/v1/rooms/{slug}/reminders/preferences"
SESSION = "/api/v1/rooms/{slug}/session"
START = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)


class FakeClock:
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
def enrolled(room, clock):
    """A client enrolled in the Home room, with its installation and grant ids."""
    room_id, slug, client = room
    response = client.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )
    assert response.status_code == 200, response.text
    installation_id = db.execute("SELECT id FROM reminder_installations").fetchone()[0]
    return room_id, slug, client, installation_id


def _rows() -> tuple[list, list]:
    return (
        db.execute("SELECT * FROM reminder_installations ORDER BY id").fetchall(),
        db.execute(
            "SELECT * FROM reminder_enrollments ORDER BY installation_id, room_id"
        ).fetchall(),
    )


# --- Fix 1: installation expiry is checked by the grant helper ------------------


def test_helper_refuses_active_when_installation_expired_and_writes_nothing(
    enrolled, clock
):
    room_id, _slug, _client, installation_id = enrolled
    # Shorten only the device; the grant and its token stay valid.
    db.execute(
        "UPDATE reminder_installations SET expires_at = '2026-11-04T10:30:00Z' "
        "WHERE id = ?",
        (installation_id,),
    )
    db.commit()
    assert identity.saved_grant_state_locked(installation_id, room_id) == "active"
    clock.advance(hours=1)
    before = _rows()

    state = identity.saved_grant_state_locked(installation_id, room_id)

    assert state == "needs_resume"
    assert _rows() == before


# --- Fix 2: cross-method idempotency --------------------------------------------


def test_patch_op_reused_for_enrollment_post_is_409_and_changes_nothing(enrolled):
    _room_id, slug, client, _installation_id = enrolled
    op_id = new_id()
    body = {"op_id": op_id, "base_revision": 1, "mode": "quiet"}
    patch = client.patch(PREFS.format(slug=slug), json=body)
    assert patch.status_code == 200
    before = _rows()

    post = client.post(
        ENROLL.format(slug=slug),
        json={"op_id": op_id, "base_revision": 1, "mode": "quiet"},
    )

    assert_error(post, 409, "op_id_reused")
    assert _rows() == before


def test_enrollment_post_op_reused_for_patch_is_409_and_changes_nothing(room, clock):
    _room_id, slug, client = room
    op_id = new_id()
    # First use: a new enrollment, with the same op_id and the same body shape.
    post = client.post(
        ENROLL.format(slug=slug),
        json={"op_id": op_id, "timezone": "Europe/Oslo", "mode": "quiet"},
    )
    assert post.status_code == 200
    before = _rows()

    patch = client.patch(
        PREFS.format(slug=slug),
        json={"op_id": op_id, "base_revision": 1, "mode": "quiet"},
    )

    assert_error(patch, 409, "op_id_reused")
    assert _rows() == before


def test_same_action_retry_still_replays_exactly(enrolled):
    _room_id, slug, client, _installation_id = enrolled
    op_id = new_id()
    body = {"op_id": op_id, "base_revision": 1, "mode": "quiet"}
    first = client.patch(PREFS.format(slug=slug), json=body)

    replay = client.patch(PREFS.format(slug=slug), json=body)

    assert replay.status_code == 200
    assert replay.json() == first.json()


def test_same_op_id_on_different_device_or_room_does_not_collide(enrolled):
    _room_id, slug, client, _installation_id = enrolled
    op_id = new_id()
    client.patch(
        PREFS.format(slug=slug),
        json={"op_id": op_id, "base_revision": 1, "mode": "quiet"},
    )
    other_device = client_for(slug)
    other_device.post(
        ENROLL.format(slug=slug), json={"op_id": new_id(), "timezone": "Europe/Oslo"}
    )

    response = other_device.patch(
        PREFS.format(slug=slug),
        json={"op_id": op_id, "base_revision": 1, "mode": "quiet"},
    )

    assert response.status_code == 200


# --- Fix 3: replays refresh the dynamic grant state inside the transaction -------


def test_patch_replay_after_sign_out_and_sign_in_reports_needs_resume(enrolled):
    _room_id, slug, client, _installation_id = enrolled
    op_id = new_id()
    body = {"op_id": op_id, "base_revision": 1, "mode": "quiet"}
    first = client.patch(PREFS.format(slug=slug), json=body)
    assert first.json()["enrollment"]["state"] == "active"
    client.delete(SESSION.format(slug=slug))
    client.post(SESSION.format(slug=slug), json={"password": "pw"})
    before = _rows()

    replay = client.patch(PREFS.format(slug=slug), json=body)

    assert replay.status_code == 200
    assert replay.json()["enrollment"]["state"] == "needs_resume"
    # Replay recomputes state only: no revision, activation or cookie change.
    assert _rows() == before
    assert "set-cookie" not in replay.headers


def test_enrollment_post_replay_after_cut_reports_needs_resume_and_keeps_cookie(
    room, clock
):
    _room_id, slug, client = room
    op_id = new_id()
    body = {"op_id": op_id, "timezone": "Europe/Oslo", "mode": "quiet"}
    assert client.post(ENROLL.format(slug=slug), json=body).status_code == 200
    client.delete(SESSION.format(slug=slug))
    # Signing in again alone does not resume: the replay still reports the cut.
    client.post(SESSION.format(slug=slug), json={"password": "pw"})
    before = _rows()

    replay = client.post(ENROLL.format(slug=slug), json=body)

    assert replay.json()["enrollment"]["state"] == "needs_resume"
    assert _rows() == before
    assert "set-cookie" not in replay.headers


def test_patch_replay_after_opt_out_reports_opted_out_and_mutates_nothing(enrolled):
    _room_id, slug, client, _installation_id = enrolled
    op_id = new_id()
    body = {"op_id": op_id, "base_revision": 1, "opted_out": True}
    client.patch(PREFS.format(slug=slug), json=body)
    before = _rows()

    replay = client.patch(PREFS.format(slug=slug), json=body)

    assert replay.json()["enrollment"]["state"] == "opted_out"
    assert _rows() == before


def test_patch_replay_after_expiry_reports_needs_resume(enrolled, clock):
    _room_id, slug, client, _installation_id = enrolled
    op_id = new_id()
    body = {"op_id": op_id, "base_revision": 1, "mode": "quiet"}
    client.patch(PREFS.format(slug=slug), json=body)
    db.execute("UPDATE reminder_enrollments SET expires_at = '2026-11-04T11:00:00Z'")
    db.commit()
    clock.advance(hours=2)
    before = _rows()

    replay = client.patch(PREFS.format(slug=slug), json=body)

    assert replay.json()["enrollment"]["state"] == "needs_resume"
    assert _rows() == before


def test_replay_helper_runs_inside_the_same_transaction(enrolled, monkeypatch):
    """The refresh runs while the replay's transaction is still open."""
    _room_id, slug, client, _installation_id = enrolled
    op_id = new_id()
    body = {"op_id": op_id, "base_revision": 1, "mode": "quiet"}
    client.patch(PREFS.format(slug=slug), json=body)
    observed = []
    real = identity.saved_grant_state_locked

    def spy(installation_id, room_id):
        observed.append(db.in_transaction)
        return real(installation_id, room_id)

    monkeypatch.setattr(identity, "saved_grant_state_locked", spy)

    client.patch(PREFS.format(slug=slug), json=body)

    assert observed == [True]


# --- Fix 4: revocation hooks are atomic with the revocation ----------------------


def test_sign_out_revocation_rolls_back_when_enrollment_update_fails(
    enrolled, monkeypatch
):
    room_id, slug, client, installation_id = enrolled
    token_before = db.execute(
        "SELECT revoked_at FROM room_access_tokens WHERE room_id = ?", (room_id,)
    ).fetchall()
    enrollment_before = _rows()[1]

    def fail(_token_hash):
        raise RuntimeError("simulated hook failure")

    monkeypatch.setattr("database_crud.disable_enrollments_for_token_locked", fail)
    token = _room_token_for(client, slug)

    with pytest.raises(RuntimeError):
        revoke_room_access_token(slug, token)

    assert (
        db.execute(
            "SELECT revoked_at FROM room_access_tokens WHERE room_id = ?", (room_id,)
        ).fetchall()
        == token_before
    )
    assert _rows()[1] == enrollment_before
    assert _rows()[0] is not None and installation_id is not None


def test_password_change_rolls_back_grant_cut_when_hook_fails(enrolled, monkeypatch):
    room_id, slug, _client, _installation_id = enrolled
    before = db.execute(
        "SELECT authorization_version, password_hash FROM rooms WHERE id = ?",
        (room_id,),
    ).fetchone()
    enrollment_before = _rows()[1]

    def fail(_room_id):
        raise RuntimeError("simulated hook failure")

    monkeypatch.setattr("database_crud.disable_room_enrollments_locked", fail)

    from database_crud import reset_room_password_by_slug

    with pytest.raises(RuntimeError):
        reset_room_password_by_slug(slug, "another-password")

    assert (
        db.execute(
            "SELECT authorization_version, password_hash FROM rooms WHERE id = ?",
            (room_id,),
        ).fetchone()
        == before
    )
    assert _rows()[1] == enrollment_before


def _room_token_for(client, slug: str) -> str:
    """The room token behind this client's cookie (test-only lookup)."""
    from room_cookies import token_cookie_name

    cookie = client.cookies.get(token_cookie_name(slug))
    return cookie
