"""Room password checks (bcrypt) run outside the database lock.

The lock is an RLock, so the test asks from another thread whether it is free.
A check that started while the lock was held would see it taken.
"""

import threading

from api_helpers import client_for

import api.room as api_room
import database_crud as crud
from database_crud import (
    authenticate_room_and_issue_token,
    create_room,
    reset_room_password_by_slug,
)
from database_setup import db


def lock_is_free() -> bool:
    """True when no other thread holds the database lock."""
    result: list[bool] = []

    def probe() -> None:
        acquired = crud._DB_LOCK.acquire(blocking=False)
        if acquired:
            crud._DB_LOCK.release()
        result.append(acquired)

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join()
    return result[0]


def record_lock_state(monkeypatch, module, name: str) -> list[bool]:
    """Wrap a password check so each call records whether the lock was free."""
    free_during_checks: list[bool] = []
    original = getattr(module, name)

    def checked(plain_password, stored_hash):
        free_during_checks.append(lock_is_free())
        return original(plain_password, stored_hash)

    monkeypatch.setattr(module, name, checked)
    return free_during_checks


def test_sign_in_checks_the_password_outside_the_lock(monkeypatch):
    _, slug = create_room("Lock room", "password")
    free = record_lock_state(monkeypatch, crud, "room_password_matches")

    assert authenticate_room_and_issue_token(slug, "password") is not None
    assert authenticate_room_and_issue_token(slug, "wrong") is None
    # An unknown room still runs one check (the dummy hash), outside the lock.
    assert authenticate_room_and_issue_token("no-such-room", "password") is None

    assert free == [True, True, True]


def test_change_password_checks_outside_the_lock(monkeypatch):
    _, slug = create_room("Change room", "password")
    client = client_for(slug, password="password")
    free = record_lock_state(monkeypatch, api_room, "room_password_matches")

    response = client.post(
        f"/api/v1/rooms/{slug}/password",
        json={"current_password": "password", "new_password": "new-password"},
    )

    assert response.status_code == 200
    assert free == [True]


def test_delete_room_checks_outside_the_lock(monkeypatch):
    room_id, slug = create_room("Delete room", "password")
    client = client_for(slug, password="password")
    free = record_lock_state(monkeypatch, api_room, "room_password_matches")

    response = client.request(
        "DELETE", f"/api/v1/rooms/{slug}", json={"password": "password"}
    )

    assert response.status_code == 204
    assert free == [True]
    assert db.execute("SELECT 1 FROM rooms WHERE id = ?", (room_id,)).fetchone() is None


def test_change_password_is_refused_when_the_password_changed_during_the_check(
    monkeypatch,
):
    _, slug = create_room("Race room", "password")
    client = client_for(slug, password="password")
    original = api_room.room_password_matches

    def other_device_resets_during_check(plain_password, stored_hash):
        result = original(plain_password, stored_hash)
        reset_room_password_by_slug(slug, "other-password")
        return result

    monkeypatch.setattr(
        api_room, "room_password_matches", other_device_resets_during_check
    )
    response = client.post(
        f"/api/v1/rooms/{slug}/password",
        json={"current_password": "password", "new_password": "new-password"},
    )

    # The other device's reset revoked this session, so the write phase refuses.
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    # The other device's password stands; the refused change wrote nothing.
    assert authenticate_room_and_issue_token(slug, "other-password") is not None
    assert authenticate_room_and_issue_token(slug, "new-password") is None


def test_delete_room_is_refused_when_the_password_changed_during_the_check(
    monkeypatch,
):
    room_id, slug = create_room("Race delete", "password")
    client = client_for(slug, password="password")
    original = api_room.room_password_matches

    def other_device_resets_during_check(plain_password, stored_hash):
        result = original(plain_password, stored_hash)
        reset_room_password_by_slug(slug, "other-password")
        return result

    monkeypatch.setattr(
        api_room, "room_password_matches", other_device_resets_during_check
    )
    response = client.request(
        "DELETE", f"/api/v1/rooms/{slug}", json={"password": "password"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert db.execute("SELECT 1 FROM rooms WHERE id = ?", (room_id,)).fetchone()
