"""Room-owned groups are editable only with room access and sync through the feed."""

import json
import secrets
import uuid

from api_helpers import assert_error, changes, default_list

from database_crud import transaction
from database_setup import db


def create_group(client, slug: str, *, name="Dinner", items=None):
    return client.post(
        f"/api/v1/rooms/{slug}/item-groups",
        json={"name": name, "items": ["beans", "Rice"] if items is None else items},
    )


def test_group_catalog_is_room_scoped_and_tracks_create_edit_delete(room, notified):
    room_id, slug, client = room
    created = create_group(client, slug)
    assert created.status_code == 201, created.text
    group = created.json()["group"]
    assert group["name"] == "Dinner"
    assert group["items"] == ["beans", "Rice"]
    after_create = group["changed_seq"]

    full = changes(client, slug, 0)
    assert full["seq"] == after_create
    assert full["groups"] == [group]
    assert full["deletions"] == []

    updated = client.put(
        f"/api/v1/rooms/{slug}/item-groups/{group['uid']}",
        json={"base_seq": group["changed_seq"], "name": "Supper", "items": ["Rice"]},
    )
    assert updated.status_code == 200, updated.text
    changed = updated.json()["group"]
    assert changed["name"] == "Supper"
    assert changed["items"] == ["Rice"]
    assert changed["changed_seq"] > after_create
    delta = changes(client, slug, after_create)
    assert delta["groups"] == [changed]

    deleted = client.request(
        "DELETE",
        f"/api/v1/rooms/{slug}/item-groups/{group['uid']}",
        json={"base_seq": changed["changed_seq"]},
    )
    assert deleted.status_code == 204, deleted.text
    removal = changes(client, slug, changed["changed_seq"])
    assert removal["groups"] == []
    assert removal["deletions"] == [{"kind": "group", "uid": group["uid"]}]
    assert changes(client, slug, 0)["groups"] == []
    assert notified == [room_id, room_id, room_id]


def test_group_names_are_case_insensitive_unique_and_validated(room):
    _room_id, slug, client = room
    first = create_group(client, slug, name="  Dinner ", items=["Milk", "Bread"])
    assert first.status_code == 201

    duplicate = create_group(client, slug, name="dinner")
    assert_error(duplicate, 409, "group_name_taken")

    empty = create_group(client, slug, name="Empty group", items=[])
    assert empty.status_code == 201
    assert empty.json()["group"]["items"] == []

    bad_items = [
        (["milk", " Milk "], "A group cannot contain the same item more than once."),
        (["  "], "Group item names cannot be empty."),
        (["x" * 101], "Group item names can be at most 100 characters."),
    ]
    for items, message in bad_items:
        response = create_group(client, slug, name="Other", items=items)
        assert_error(response, 422, "invalid_request")
        assert response.json()["error"]["message"] == message

    long_name = create_group(client, slug, name="x" * 101)
    assert_error(long_name, 422, "invalid_request")
    assert (
        long_name.json()["error"]["message"]
        == "Group name can be at most 100 characters."
    )


def test_stale_group_edit_and_delete_are_rejected_without_losing_changes(room):
    _room_id, slug, client = room
    group = create_group(client, slug).json()["group"]
    first_edit = client.put(
        f"/api/v1/rooms/{slug}/item-groups/{group['uid']}",
        json={"base_seq": group["changed_seq"], "name": "Updated", "items": ["Rice"]},
    )
    assert first_edit.status_code == 200
    latest = first_edit.json()["group"]

    stale_edit = client.put(
        f"/api/v1/rooms/{slug}/item-groups/{group['uid']}",
        json={"base_seq": group["changed_seq"], "name": "Mine", "items": ["Beans"]},
    )
    assert_error(stale_edit, 409, "group_changed_meanwhile")
    assert "Reload" in stale_edit.json()["error"]["message"]
    [current] = changes(client, slug, 0)["groups"]
    assert current == latest

    stale_delete = client.request(
        "DELETE",
        f"/api/v1/rooms/{slug}/item-groups/{group['uid']}",
        json={"base_seq": group["changed_seq"]},
    )
    assert_error(stale_delete, 409, "group_changed_meanwhile")
    [still_there] = changes(client, slug, 0)["groups"]
    assert still_there == latest


def test_group_count_limit_is_checked_inside_write_transaction(room):
    room_id, slug, client = room
    with transaction(write=True):
        for number in range(100):
            db.execute(
                "INSERT INTO item_groups (uid, room_id, name, name_key, items_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    room_id,
                    f"Group {number}",
                    f"group {number}",
                    json.dumps([f"item {number}"]),
                ),
            )

    response = create_group(client, slug, name="101st")
    assert_error(response, 422, "invalid_request")
    assert (
        response.json()["error"]["message"] == "A room can have at most 100 item groups"
    )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM item_groups WHERE room_id = ? AND deleted = 0",
            (room_id,),
        ).fetchone()[0]
        == 100
    )


def test_room_group_routes_and_public_share_feed_do_not_disclose_catalog(room):
    _room_id, slug, client = room
    group = create_group(client, slug, name="Private recipe").json()["group"]
    list_uid = default_list()[1]
    share_token = secrets.token_urlsafe(32)
    with transaction(write=True):
        db.execute(
            "UPDATE lists SET share_token = ? WHERE uid = ?", (share_token, list_uid)
        )

    from starlette.testclient import TestClient

    import main

    public = TestClient(
        main.app,
        base_url="https://testserver",
        headers={"Origin": "https://testserver"},
    )
    public_feed = public.get(f"/api/v1/share/{share_token}/changes?since=0")
    assert public_feed.status_code == 200
    assert public_feed.json()["groups"] == []
    assert group["name"] not in public_feed.text

    denied = public.post(
        f"/api/v1/rooms/{slug}/item-groups",
        json={"name": "Leaked", "items": ["secret"]},
    )
    assert_error(denied, 401, "not_authenticated")
    no_share_management = public.get(f"/api/v1/share/{share_token}/item-groups")
    assert no_share_management.status_code == 404


def test_group_management_never_uses_another_room_group(room):
    _room_id, slug, client = room
    group = create_group(client, slug).json()["group"]
    foreign_uid = str(uuid.uuid4())
    with transaction(write=True):
        db.execute(
            "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
            ("Other", "other-room", "unused"),
        )
        other_room_id = db.execute(
            "SELECT id FROM rooms WHERE slug = 'other-room'"
        ).fetchone()[0]
        db.execute(
            "INSERT INTO item_groups (uid, room_id, name, name_key, items_json) "
            "VALUES (?, ?, 'Foreign', 'foreign', '[\"item\"]')",
            (foreign_uid, other_room_id),
        )

    response = client.put(
        f"/api/v1/rooms/{slug}/item-groups/{foreign_uid}",
        json={"base_seq": 1, "name": "Stolen", "items": ["item"]},
    )
    assert_error(response, 404, "group_unavailable")
    [stored] = changes(client, slug, 0)["groups"]
    assert stored == group
