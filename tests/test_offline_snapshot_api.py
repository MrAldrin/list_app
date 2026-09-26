import sqlite3
import threading

from starlette.testclient import TestClient

import database_crud
import main
from database_crud import (
    MAX_OFFLINE_SNAPSHOT_BYTES,
    MAX_OFFLINE_SNAPSHOT_ITEMS,
    MAX_OFFLINE_SNAPSHOT_LISTS,
    authenticate_room_and_issue_token,
    revoke_room_access_token,
    update_room_password,
    validate_room_access_token,
)
from database_setup import db
from room_cookies import token_cookie_name

ORIGIN = "https://testserver"
ENDPOINT = "/api/offline/rooms/{slug}/snapshot"
SAME_ORIGIN_HEADERS = {"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"}


def credentials(slug=None):
    room = (
        db.execute("SELECT id, slug FROM rooms WHERE slug = ?", (slug,)).fetchone()
        if slug is not None
        else db.execute("SELECT id, slug FROM rooms ORDER BY id LIMIT 1").fetchone()
    )
    return room[0], room[1], authenticate_room_and_issue_token(room[1], "pw")[1]


def test_valid_cookie_snapshot_is_versioned_complete_and_private():
    room_id, slug, token = credentials()
    room_password_hash = db.execute(
        "SELECT password_hash FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]
    db.execute("UPDATE rooms SET name = ? WHERE id = ?", ("家 & Pantry", room_id))
    list_id = db.execute(
        "SELECT id FROM lists WHERE room_id = ?", (room_id,)
    ).fetchone()[0]
    db.execute(
        "UPDATE lists SET name = ?, list_tags = ?, share_token = ? WHERE id = ?",
        ("Fruit <fresh>", '["produce"]', "private-share-secret", list_id),
    )
    db.execute(
        "INSERT INTO lists (name, list_tags, room_id) VALUES (?, ?, ?)",
        ("Empty & <list>", '["later"]', room_id),
    )
    db.execute(
        """
        INSERT INTO items (name, done, list_id, active_tags, description, quantity)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("りんご & <fresh>", 0, list_id, '["organic"]', "red & crisp", 3),
    )
    db.execute(
        """
        INSERT INTO items (name, done, list_id, active_tags, description, quantity)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("Finished", 1, list_id, "[]", "done item", 1),
    )
    db.commit()

    client = TestClient(main.app, base_url=ORIGIN)
    response = client.get(
        ENDPOINT.format(slug=slug),
        headers={
            **SAME_ORIGIN_HEADERS,
            "Cookie": f"{token_cookie_name(slug)}={token}",
        },
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json() == {
        "schema_version": 1,
        "room": {"slug": slug, "name": "家 & Pantry"},
        "lists": [
            {
                "name": "Empty & <list>",
                "list_tags": ["later"],
                "items": [],
            },
            {
                "name": "Fruit <fresh>",
                "list_tags": ["produce"],
                "items": [
                    {
                        "name": "りんご & <fresh>",
                        "done": False,
                        "active_tags": ["organic"],
                        "description": "red & crisp",
                        "quantity": 3,
                    },
                    {
                        "name": "Finished",
                        "done": True,
                        "active_tags": [],
                        "description": "done item",
                        "quantity": 1,
                    },
                ],
            },
        ],
    }
    body = response.text
    assert token not in body
    assert room_password_hash not in body
    assert "private-share-secret" not in body
    assert "password_hash" not in body
    assert "share_token" not in body


def test_fallback_header_is_accepted_but_query_tokens_are_not():
    _, slug, token = credentials()
    client = TestClient(main.app, base_url=ORIGIN)

    response = client.get(
        ENDPOINT.format(slug=slug),
        headers={**SAME_ORIGIN_HEADERS, "X-Listapp-Room-Token": token},
    )
    assert response.status_code == 200
    assert response.json()["room"]["slug"] == slug

    response = client.get(
        f"{ENDPOINT.format(slug=slug)}?token={token}", headers=SAME_ORIGIN_HEADERS
    )
    assert response.status_code == 401
    assert "no-store" in response.headers["cache-control"]


def test_no_room_token_or_admin_session_is_not_authorization():
    _, slug, _ = credentials()
    response = TestClient(main.app, base_url=ORIGIN).get(
        ENDPOINT.format(slug=slug), headers=SAME_ORIGIN_HEADERS
    )
    assert response.status_code == 401
    assert response.json() == {
        "schema_version": 1,
        "error": "room_authorization_required",
    }


def test_wrong_room_public_share_revoked_and_deleted_grants_are_denied():
    _, slug, room_token = credentials()
    password_hash = db.execute(
        "SELECT password_hash FROM rooms WHERE slug = ?", (slug,)
    ).fetchone()[0]
    db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
        ("Other", "other-room", password_hash),
    )
    db.commit()
    other_token = authenticate_room_and_issue_token("other-room", "pw")[1]
    room_id = db.execute("SELECT id FROM rooms WHERE slug = ?", (slug,)).fetchone()[0]
    db.execute(
        "UPDATE lists SET share_token = ? WHERE room_id = ?",
        ("public-share-secret", room_id),
    )
    db.commit()
    client = TestClient(main.app, base_url=ORIGIN)

    for token in ("not-a-token", other_token, "public-share-secret"):
        response = client.get(
            ENDPOINT.format(slug=slug),
            headers={**SAME_ORIGIN_HEADERS, "X-Listapp-Room-Token": token},
        )
        assert response.status_code == 401
        assert response.json()["error"] == "room_authorization_required"

    # Model the grant being revoked after an authorized room page rendered.
    assert validate_room_access_token(slug, room_token) is not None
    revoke_room_access_token(slug, room_token)
    revoked = client.get(
        ENDPOINT.format(slug=slug),
        headers={**SAME_ORIGIN_HEADERS, "X-Listapp-Room-Token": room_token},
    )
    assert revoked.status_code == 401

    deleted_slug = slug
    deleted_token = authenticate_room_and_issue_token(deleted_slug, "pw")[1]
    deleted_room_id = db.execute(
        "SELECT id FROM rooms WHERE slug = ?", (deleted_slug,)
    ).fetchone()[0]
    db.execute(
        "DELETE FROM items WHERE list_id IN (SELECT id FROM lists WHERE room_id = ?)",
        (deleted_room_id,),
    )
    db.execute("DELETE FROM lists WHERE room_id = ?", (deleted_room_id,))
    db.execute("DELETE FROM room_access_tokens WHERE room_id = ?", (deleted_room_id,))
    db.execute("DELETE FROM rooms WHERE id = ?", (deleted_room_id,))
    db.commit()
    deleted = client.get(
        ENDPOINT.format(slug=deleted_slug),
        headers={**SAME_ORIGIN_HEADERS, "X-Listapp-Room-Token": deleted_token},
    )
    assert deleted.status_code == 401


def test_same_origin_policy_is_checked_when_browser_metadata_is_present():
    _, slug, token = credentials()
    client = TestClient(main.app, base_url=ORIGIN)
    path = ENDPOINT.format(slug=slug)
    token_header = {"X-Listapp-Room-Token": token}

    for headers in (
        {**token_header, "Origin": "https://attacker.example"},
        {**token_header, "Sec-Fetch-Site": "same-site"},
        {**token_header, "Sec-Fetch-Site": "cross-site"},
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 403
        assert response.json() == {
            "schema_version": 1,
            "error": "same_origin_required",
        }
        assert response.headers["cache-control"] == "no-store"


def test_database_failure_is_transient_503_not_an_empty_room(monkeypatch):
    _, slug, token = credentials()

    def database_unavailable(*_args):
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(main, "get_authorized_room_snapshot", database_unavailable)
    response = TestClient(main.app, base_url=ORIGIN).get(
        ENDPOINT.format(slug=slug),
        headers={**SAME_ORIGIN_HEADERS, "X-Listapp-Room-Token": token},
    )
    assert response.status_code == 503
    assert response.json() == {
        "schema_version": 1,
        "error": "snapshot_unavailable",
    }


def test_snapshot_bounds_reject_the_whole_response():
    room_id, slug, token = credentials()
    list_id = db.execute(
        "SELECT id FROM lists WHERE room_id = ?", (room_id,)
    ).fetchone()[0]
    db.execute(
        "INSERT INTO items (name, description, list_id) VALUES (?, ?, ?)",
        ("large", "x" * (MAX_OFFLINE_SNAPSHOT_BYTES + 1), list_id),
    )
    db.commit()
    response = TestClient(main.app, base_url=ORIGIN).get(
        ENDPOINT.format(slug=slug),
        headers={**SAME_ORIGIN_HEADERS, "X-Listapp-Room-Token": token},
    )
    assert response.status_code == 413
    assert response.json() == {"schema_version": 1, "error": "snapshot_too_large"}
    assert "lists" not in response.json()


def test_snapshot_list_and_item_count_limits_are_enforced():
    # The complete response is capped at 200 lists, 5,000 items, and 1 MiB.
    room_id, slug, token = credentials()
    db.executemany(
        "INSERT INTO lists (name, room_id) VALUES (?, ?)",
        [(f"list-{index}", room_id) for index in range(MAX_OFFLINE_SNAPSHOT_LISTS)],
    )
    db.commit()
    client = TestClient(main.app, base_url=ORIGIN)
    response = client.get(
        ENDPOINT.format(slug=slug),
        headers={**SAME_ORIGIN_HEADERS, "X-Listapp-Room-Token": token},
    )
    assert response.status_code == 413

    db.execute("DELETE FROM lists WHERE name LIKE 'list-%'")
    list_id = db.execute(
        "SELECT id FROM lists WHERE room_id = ?", (room_id,)
    ).fetchone()[0]
    db.executemany(
        "INSERT INTO items (name, list_id) VALUES (?, ?)",
        [(f"item-{index}", list_id) for index in range(MAX_OFFLINE_SNAPSHOT_ITEMS + 1)],
    )
    db.commit()
    response = client.get(
        ENDPOINT.format(slug=slug),
        headers={**SAME_ORIGIN_HEADERS, "X-Listapp-Room-Token": token},
    )
    assert response.status_code == 413


def test_concurrent_password_reset_cannot_split_authorization_and_snapshot(monkeypatch):
    room_id, slug, token = credentials()
    reset_started = threading.Event()
    reset_done = threading.Event()
    original_check = database_crud._valid_room_id_for_token_locked

    reset_threads = []

    def reset_password():
        reset_started.set()
        update_room_password(room_id, "new-password")
        reset_done.set()

    def start_reset_after_authorization(room_slug, candidate):
        authorized_id = original_check(room_slug, candidate)
        thread = threading.Thread(target=reset_password)
        reset_threads.append(thread)
        thread.start()
        assert reset_started.wait(timeout=2)
        # The snapshot helper still owns the database lock and read transaction.
        assert not reset_done.wait(timeout=0.05)
        return authorized_id

    monkeypatch.setattr(
        database_crud,
        "_valid_room_id_for_token_locked",
        start_reset_after_authorization,
    )
    snapshot = database_crud.get_authorized_room_snapshot(slug, token)
    assert snapshot is not None
    assert snapshot["room"]["slug"] == slug
    assert reset_done.wait(timeout=5)
    for thread in reset_threads:
        thread.join(timeout=5)
    monkeypatch.setattr(
        database_crud, "_valid_room_id_for_token_locked", original_check
    )
    assert database_crud.validate_room_access_token(slug, token) is None


def test_empty_room_snapshot_is_a_successful_replacement():
    room_id, slug, token = credentials()
    db.execute(
        "DELETE FROM items WHERE list_id IN (SELECT id FROM lists WHERE room_id = ?)",
        (room_id,),
    )
    db.execute("DELETE FROM lists WHERE room_id = ?", (room_id,))
    db.commit()

    response = TestClient(main.app, base_url=ORIGIN).get(
        ENDPOINT.format(slug=slug),
        headers={**SAME_ORIGIN_HEADERS, "X-Listapp-Room-Token": token},
    )
    assert response.status_code == 200
    assert response.json() == {
        "schema_version": 1,
        "room": {"slug": slug, "name": "Home"},
        "lists": [],
    }


def test_invalid_persisted_tags_fail_transiently_instead_of_silently_dropping_data():
    _, slug, token = credentials()
    db.execute("UPDATE lists SET list_tags = ?", ("not-json",))
    db.commit()
    response = TestClient(main.app, base_url=ORIGIN).get(
        ENDPOINT.format(slug=slug),
        headers={**SAME_ORIGIN_HEADERS, "X-Listapp-Room-Token": token},
    )
    assert response.status_code == 503
    assert response.json()["error"] == "snapshot_unavailable"
