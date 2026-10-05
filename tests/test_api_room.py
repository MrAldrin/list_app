"""Room management in the JSON API: rename (op), change password, delete room.

The rules are NiceGUI's (docs/api.md, "Room management").
"""

from http.cookies import SimpleCookie
from unittest.mock import patch

import pytest
from api_helpers import (
    assert_error,
    changes,
    client_for,
    default_list,
    home,
    new_id,
    op,
    processed_ops_count,
    send,
)

import database_crud as crud
from database_setup import db
from room_cookies import LAST_ROOM_COOKIE, token_cookie_name


def set_cookies(response) -> dict[str, SimpleCookie]:
    cookies = {}
    for header in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        cookie.load(header)
        name = next(iter(cookie))
        cookies[name] = cookie[name]
    return cookies


def room_name(room_id: int) -> str:
    return db.execute("SELECT name FROM rooms WHERE id = ?", (room_id,)).fetchone()[0]


def change_password(client, slug: str, current: str = "pw", new: str = "new-pw"):
    return client.post(
        f"/api/v1/rooms/{slug}/password",
        json={"current_password": current, "new_password": new},
    )


def delete_room(client, slug: str, password: str = "pw"):
    return client.request(
        "DELETE", f"/api/v1/rooms/{slug}", json={"password": password}
    )


def other_room() -> tuple[int, str]:
    return crud.create_room("Cabin", "cabin-pw")


# Rename (an op)


def test_rename_room_trims_keeps_case_and_shows_in_the_feed():
    room_id, slug = home()
    client = client_for(slug)
    before = changes(client, slug, 0)["seq"]

    response = op(
        client, slug, {"op_id": new_id(), "type": "room.rename", "name": "  Our  Flat "}
    )

    assert response["status"] == "applied"
    assert response["result"] == {}
    assert response["seq"] > before
    assert room_name(room_id) == "Our  Flat"
    feed = changes(client, slug, before)
    assert feed["room"] == {"slug": slug, "name": "Our  Flat"}
    # The slug stays, so links keep working.
    assert client.get(f"/api/v1/rooms/{slug}/session").status_code == 200


def test_rename_room_rejects_a_blank_name():
    room_id, slug = home()
    client = client_for(slug)
    seq = changes(client, slug, 0)["seq"]

    response = op(client, slug, {"op_id": new_id(), "type": "room.rename", "name": " "})

    assert response["status"] == "rejected"
    assert response["code"] == "invalid_name"
    assert response["message"] == "Name cannot be empty"
    assert response["seq"] == seq
    assert room_name(room_id) == "Home"


def test_room_names_need_not_be_unique():
    _, slug = home()
    other_room()
    response = op(
        client_for(slug),
        slug,
        {"op_id": new_id(), "type": "room.rename", "name": "Cabin"},
    )
    assert response["status"] == "applied"


def test_rename_room_without_access_is_401_and_changes_nothing():
    room_id, slug = home()
    response = send(
        client_for(), slug, {"op_id": new_id(), "type": "room.rename", "name": "X"}
    )
    assert_error(response, 401, "not_authenticated")
    assert room_name(room_id) == "Home"


def test_rename_room_replays_by_op_id():
    room_id, slug = home()
    client = client_for(slug)
    body = {"op_id": new_id(), "type": "room.rename", "name": "First"}
    first = op(client, slug, body)
    op(client, slug, {"op_id": new_id(), "type": "room.rename", "name": "Second"})

    assert op(client, slug, body) == first
    assert room_name(room_id) == "Second"
    assert_error(send(client, slug, {**body, "name": "Other"}), 409, "op_id_reused")


def test_rename_room_tells_nicegui_and_streams():
    room_id, slug = home()
    client = client_for(slug)
    with patch("api.ops.notify_room_changed") as notify:
        op(client, slug, {"op_id": new_id(), "type": "room.rename", "name": "New"})
    notify.assert_called_once_with(room_id)


# Change password


def test_change_password_revokes_old_tokens_and_signs_this_browser_in_again():
    room_id, slug = home()
    client = client_for(slug)
    other_device = client_for(slug)

    response = change_password(client, slug)

    assert response.status_code == 200
    assert response.json() == {"room": {"slug": slug, "name": "Home"}}
    assert response.headers["cache-control"] == "no-store"
    cookies = set_cookies(response)
    assert set(cookies) == {token_cookie_name(slug), LAST_ROOM_COOKIE}
    token = cookies[token_cookie_name(slug)]
    assert token["httponly"] is True
    assert token["secure"] is True
    assert token.value not in response.text
    # This browser stays signed in with the new token; others are signed out.
    assert client.get(f"/api/v1/rooms/{slug}/session").status_code == 200
    assert_error(
        other_device.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated"
    )
    assert crud.verify_room(slug, "new-pw") == room_id
    assert crud.verify_room(slug, "pw") is None


def test_change_password_with_a_wrong_current_password_changes_nothing():
    room_id, slug = home()
    client = client_for(slug)
    tokens = db.execute("SELECT * FROM room_access_tokens").fetchall()

    response = change_password(client, slug, current="wrong")

    assert_error(response, 403, "wrong_password")
    assert response.json()["error"]["message"] == "Incorrect current password"
    assert "set-cookie" not in response.headers
    assert crud.verify_room(slug, "pw") == room_id
    assert db.execute("SELECT * FROM room_access_tokens").fetchall() == tokens
    assert client.get(f"/api/v1/rooms/{slug}/session").status_code == 200


@pytest.mark.parametrize(
    ("new", "message"),
    [
        ("", "New password cannot be empty"),
        ("   ", "New password cannot be empty"),
        ("x" * 73, "The password cannot be longer than 72 bytes"),
        ("\N{LATIN SMALL LETTER O WITH DIAERESIS}" * 37, "longer than 72 bytes"),
    ],
)
def test_change_password_rejects_a_blank_or_too_long_new_password(new, message):
    room_id, slug = home()
    response = change_password(client_for(slug), slug, new=new)
    assert_error(response, 422, "invalid_request")
    assert message in response.json()["error"]["message"]
    assert crud.verify_room(slug, "pw") == room_id


def test_change_password_keeps_spaces_inside_and_around_the_new_password():
    room_id, slug = home()
    assert change_password(client_for(slug), slug, new=" a b ").status_code == 200
    assert crud.verify_room(slug, " a b ") == room_id
    assert crud.verify_room(slug, "a b") is None


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"current_password": "pw"},
        {"current_password": "pw", "new_password": 1},
        {"current_password": "pw", "new_password": "n", "extra": 1},
        {"current_password": "x" * 1025, "new_password": "n"},
    ],
)
def test_change_password_with_a_bad_body_is_422(body):
    room_id, slug = home()
    response = client_for(slug).post(f"/api/v1/rooms/{slug}/password", json=body)
    assert_error(response, 422, "invalid_request")
    assert crud.verify_room(slug, "pw") == room_id


def test_change_password_needs_room_access_first():
    room_id, slug = home()
    # The right password without the room cookie: still 401, like a wrong room.
    no_cookie = change_password(client_for(), slug)
    unknown = change_password(client_for(), "no-such-room")
    assert_error(no_cookie, 401, "not_authenticated")
    assert_error(unknown, 401, "not_authenticated")
    assert no_cookie.content == unknown.content
    assert crud.verify_room(slug, "pw") == room_id


def test_change_password_with_another_rooms_cookie_is_401():
    _, slug = home()
    _, cabin = other_room()
    client = client_for(cabin, password="cabin-pw")
    assert_error(change_password(client, slug), 401, "not_authenticated")


def test_change_password_needs_same_origin():
    room_id, slug = home()
    client = client_for(slug)
    response = client.post(
        f"/api/v1/rooms/{slug}/password",
        json={"current_password": "pw", "new_password": "new"},
        headers={"Origin": "https://evil.example"},
    )
    assert_error(response, 403, "forbidden_origin")
    assert crud.verify_room(slug, "pw") == room_id


def test_change_password_wakes_the_room_streams_and_stores_no_op():
    room_id, slug = home()
    client = client_for(slug)
    with patch("api.room.wake_streams") as wake:
        assert change_password(client, slug).status_code == 200
    wake.assert_called_once_with(room_id)
    assert processed_ops_count() == 0


def test_a_wrong_password_does_not_wake_streams():
    _, slug = home()
    with patch("api.room.wake_streams") as wake:
        change_password(client_for(slug), slug, current="wrong")
    wake.assert_not_called()


def test_password_change_on_plain_http_uses_plain_cookies():
    _, slug = home()
    from starlette.testclient import TestClient

    import main

    http = "http://testserver"
    client = TestClient(
        main.app, base_url=http, headers={"Origin": http}, raise_server_exceptions=False
    )
    assert (
        client.post(
            f"/api/v1/rooms/{slug}/session", json={"password": "pw"}
        ).status_code
        == 200
    )
    response = change_password(client, slug)
    assert response.status_code == 200
    cookies = set_cookies(response)
    assert all(not cookie["secure"] for cookie in cookies.values())
    assert client.get(f"/api/v1/rooms/{slug}/session").status_code == 200


# Delete room


def test_delete_room_removes_its_lists_items_tokens_and_clears_cookies():
    room_id, slug = home()
    list_id, _ = default_list()
    crud.add_item_with_state("milk", list_id, False, [])
    cabin_id, cabin = other_room()
    cabin_list, _ = crud.create_list("Cabin list", cabin_id)
    client = client_for(slug)
    op(client, slug, {"op_id": new_id(), "type": "room.rename", "name": "Doomed"})
    other_device = client_for(slug)

    response = delete_room(client, slug)

    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    cookies = set_cookies(response)
    assert set(cookies) == {token_cookie_name(slug), LAST_ROOM_COOKIE}
    assert all(cookie.value == "" for cookie in cookies.values())
    for table, column in [
        ("rooms", "id"),
        ("lists", "room_id"),
        ("room_access_tokens", "room_id"),
        ("processed_ops", "room_id"),
        ("deletions", "room_id"),
    ]:
        count = db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (room_id,)
        ).fetchone()[0]
        assert count == 0, table
    assert db.execute(
        "SELECT COUNT(*) FROM items WHERE list_id = ?", (list_id,)
    ).fetchone() == (0,)
    # Other rooms keep everything.
    assert crud.get_room_details_by_slug(cabin)["id"] == cabin_id
    assert [row[0] for row in crud.get_lists(cabin_id)] == [cabin_list]
    # Signed out everywhere; signing in looks like a wrong password.
    assert_error(
        other_device.get(f"/api/v1/rooms/{slug}/session"), 401, "not_authenticated"
    )
    assert_error(
        client.post(f"/api/v1/rooms/{slug}/session", json={"password": "pw"}),
        401,
        "invalid_password",
    )


def test_delete_room_keeps_a_last_room_cookie_of_another_room():
    _, slug = home()
    _, cabin = other_room()
    client = client_for(slug)
    client.post(f"/api/v1/rooms/{cabin}/session", json={"password": "cabin-pw"})
    assert client.get("/api/v1/last-room").json() == {"slug": cabin}

    response = delete_room(client, slug)

    assert response.status_code == 204
    assert set(set_cookies(response)) == {token_cookie_name(slug)}
    assert client.get("/api/v1/last-room").json() == {"slug": cabin}


def test_delete_room_with_a_wrong_password_keeps_everything():
    room_id, slug = home()
    client = client_for(slug)
    before = db.execute("SELECT COUNT(*) FROM lists").fetchone()

    response = delete_room(client, slug, password="wrong")

    assert_error(response, 403, "wrong_password")
    assert response.json()["error"]["message"] == "Incorrect password"
    assert "set-cookie" not in response.headers
    assert crud.get_room_details_by_slug(slug)["id"] == room_id
    assert db.execute("SELECT COUNT(*) FROM lists").fetchone() == before
    assert client.get(f"/api/v1/rooms/{slug}/session").status_code == 200


def test_delete_room_needs_room_access_first():
    room_id, slug = home()
    no_cookie = delete_room(client_for(), slug)
    unknown = delete_room(client_for(), "no-such-room")
    assert_error(no_cookie, 401, "not_authenticated")
    assert_error(unknown, 401, "not_authenticated")
    assert no_cookie.content == unknown.content
    assert crud.get_room_details_by_slug(slug)["id"] == room_id


def test_delete_room_with_another_rooms_cookie_is_401():
    room_id, slug = home()
    _, cabin = other_room()
    client = client_for(cabin, password="cabin-pw")
    # The Home password is right, but this browser has no Home access.
    assert_error(delete_room(client, slug), 401, "not_authenticated")
    assert crud.get_room_details_by_slug(slug)["id"] == room_id


@pytest.mark.parametrize(
    "body", [{}, {"password": 1}, {"password": "pw", "x": 1}, {"password": "x" * 1025}]
)
def test_delete_room_with_a_bad_body_is_422(body):
    room_id, slug = home()
    response = client_for(slug).request("DELETE", f"/api/v1/rooms/{slug}", json=body)
    assert_error(response, 422, "invalid_request")
    assert crud.get_room_details_by_slug(slug)["id"] == room_id


def test_delete_room_without_a_body_is_refused():
    room_id, slug = home()
    response = client_for(slug).delete(f"/api/v1/rooms/{slug}")
    assert response.status_code == 400
    assert crud.get_room_details_by_slug(slug)["id"] == room_id


def test_delete_room_needs_same_origin():
    room_id, slug = home()
    response = client_for(slug).request(
        "DELETE",
        f"/api/v1/rooms/{slug}",
        json={"password": "pw"},
        headers={"Origin": "https://evil.example"},
    )
    assert_error(response, 403, "forbidden_origin")
    assert crud.get_room_details_by_slug(slug)["id"] == room_id


def test_delete_room_wakes_its_streams():
    room_id, slug = home()
    with patch("api.room.wake_streams") as wake:
        assert delete_room(client_for(slug), slug).status_code == 204
    wake.assert_called_once_with(room_id)


def test_a_failed_room_delete_rolls_back_and_is_503():
    room_id, slug = home()
    client = client_for(slug)
    db.execute(
        "CREATE TEMP TRIGGER fail_room_delete BEFORE DELETE ON rooms "
        "BEGIN SELECT RAISE(ABORT, 'injected delete failure'); END"
    )
    try:
        response = delete_room(client, slug)
    finally:
        db.execute("DROP TRIGGER fail_room_delete")
    assert_error(response, 503, "unavailable")
    assert not db.in_transaction
    assert crud.get_room_details_by_slug(slug)["id"] == room_id
    assert db.execute(
        "SELECT COUNT(*) FROM lists WHERE room_id = ?", (room_id,)
    ).fetchone() == (1,)
    assert client.get(f"/api/v1/rooms/{slug}/session").status_code == 200


def test_room_writes_are_not_reachable_over_http_get():
    _, slug = home()
    client = client_for(slug)
    assert client.get(f"/api/v1/rooms/{slug}").status_code == 405
    assert client.get(f"/api/v1/rooms/{slug}/password").status_code == 405
