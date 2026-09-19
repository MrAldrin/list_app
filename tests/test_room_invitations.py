import hashlib
import sqlite3

import pytest

import room_invitations as invitations
from database_crud import (
    authenticate_room_and_issue_token,
    get_rooms,
    validate_room_access_token,
    verify_room,
)
from database_setup import db


def test_invitation_is_random_hashed_and_valid_for_seven_days(monkeypatch):
    monkeypatch.setattr(invitations.time, "time", lambda: 1000)
    invitation_id, token = invitations.create_invitation()
    _, other = invitations.create_invitation()
    assert len(token) >= 43 and token != other
    stored = db.execute(
        "SELECT token_hash, created_at, expires_at FROM room_invitations WHERE id = ?",
        (invitation_id,),
    ).fetchone()
    assert stored == (hashlib.sha256(token.encode()).hexdigest(), 1000, 605800)
    assert token not in str(invitations.get_invitations())
    monkeypatch.setattr(invitations.time, "time", lambda: 605799)
    assert invitations.invitation_is_active(token)
    monkeypatch.setattr(invitations.time, "time", lambda: 605800)
    assert not invitations.invitation_is_active(token)
    with pytest.raises(invitations.InvitationUnavailable):
        invitations.create_room_from_invitation(token, "Late", "password")


def test_reuse_creates_separate_rooms_without_authorizing_other_rooms():
    _, token = invitations.create_invitation()
    first = invitations.create_room_from_invitation(token, " First ", "first-pw")
    second = invitations.create_room_from_invitation(token, "First", "second-pw")
    assert first != second
    assert verify_room(first, "first-pw")
    assert not verify_room(second, "first-pw")
    assert not validate_room_access_token(first, token)
    _, room_token = authenticate_room_and_issue_token(first, "first-pw")
    assert room_token
    assert not validate_room_access_token(second, room_token)
    assert any(room["slug"] == first for room in get_rooms())


def test_revocation_blocks_creation_but_not_existing_rooms():
    invitation_id, token = invitations.create_invitation()
    slug = invitations.create_room_from_invitation(token, "Existing", "pw")
    invitations.revoke_invitation(invitation_id)
    invitations.revoke_invitation(invitation_id)
    assert not invitations.invitation_is_active(token)
    assert invitations.get_invitations()[0]["revoked_at"] is not None
    with pytest.raises(invitations.InvitationUnavailable):
        invitations.create_room_from_invitation(token, "Denied", "pw")
    assert verify_room(slug, "pw")


@pytest.mark.parametrize("token", ["", "wrong", "' OR 1=1 --"])
def test_invalid_tokens_never_create_rooms(token):
    before = get_rooms()
    with pytest.raises(invitations.InvitationUnavailable):
        invitations.create_room_from_invitation(token, "Denied", "pw")
    assert get_rooms() == before


@pytest.mark.parametrize(
    ("name", "password"),
    [(" ", "pw"), ("x" * 101, "pw"), ("Room", " "), ("Room", "é" * 37)],
)
def test_invalid_inputs_do_not_create_rooms(name, password):
    _, token = invitations.create_invitation()
    before = get_rooms()
    with pytest.raises(ValueError):
        invitations.create_room_from_invitation(token, name, password)
    assert get_rooms() == before
    assert invitations.invitation_is_active(token)


@pytest.mark.parametrize("invalidate", ["expire", "revoke"])
def test_rechecks_invitation_after_password_hashing(monkeypatch, invalidate):
    monkeypatch.setattr(invitations.time, "time", lambda: 1000)
    invitation_id, token = invitations.create_invitation()
    original = invitations.bcrypt.hashpw

    def hash_and_invalidate(*args):
        result = original(*args)
        if invalidate == "expire":
            monkeypatch.setattr(invitations.time, "time", lambda: 605800)
        else:
            invitations.revoke_invitation(invitation_id)
        return result

    monkeypatch.setattr(invitations.bcrypt, "hashpw", hash_and_invalidate)
    before = get_rooms()
    with pytest.raises(invitations.InvitationUnavailable):
        invitations.create_room_from_invitation(token, "Denied", "pw")
    assert get_rooms() == before
    assert not db.in_transaction


def test_failed_insert_rolls_back_without_consuming_invitation(monkeypatch):
    _, token = invitations.create_invitation()
    existing_slug = get_rooms()[0]["slug"]
    monkeypatch.setattr(invitations.secrets, "token_urlsafe", lambda _: existing_slug)
    before = get_rooms()
    with pytest.raises(sqlite3.IntegrityError):
        invitations.create_room_from_invitation(token, "Collision", "pw")
    assert not db.in_transaction
    assert get_rooms() == before
    assert invitations.invitation_is_active(token)
