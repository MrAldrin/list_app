"""Length limits on user text (docs/item-writes.md, "Field rules")."""

from collections.abc import Callable
from typing import Any

import pytest
from api_helpers import add_item, admin, client_for, default_list, home, new_id, op

from database_setup import db

NAME, DESCRIPTION, TAG = 100, 1000, 30

# Each case: op type, fields (given a list uid, an item uid and the text),
# which limit applies, and the message prefix.
Fields = Callable[[str, str, str], dict[str, Any]]
CASES: list[tuple[str, Fields, int, str]] = [
    ("room.rename", lambda lst, item, text: {"name": text}, NAME, "Name"),
    ("list.create", lambda lst, item, text: {"name": text}, NAME, "Name"),
    (
        "list.rename",
        lambda lst, item, text: {"list_uid": lst, "name": text, "base_seq": 0},
        NAME,
        "Name",
    ),
    (
        "list.tag_add",
        lambda lst, item, text: {"list_uid": lst, "tag": text},
        TAG,
        "Tag",
    ),
    ("item.add", lambda lst, item, text: {"list_uid": lst, "name": text}, NAME, "Name"),
    (
        "item.edit",
        lambda lst, item, text: {
            "list_uid": lst,
            "item_uid": item,
            "name": text,
            "description": "",
            "base_seq": 0,
        },
        NAME,
        "Name",
    ),
    (
        "item.edit",
        lambda lst, item, text: {
            "list_uid": lst,
            "item_uid": item,
            "name": "milk",
            "description": text,
            "base_seq": 0,
        },
        DESCRIPTION,
        "Description",
    ),
    (
        "item.restore",
        lambda lst, item, text: {
            "list_uid": lst,
            "name": text,
            "done": False,
            "tags": [],
            "description": "",
            "quantity": 1,
            "completed_at": None,
        },
        NAME,
        "Name",
    ),
    (
        "item.restore",
        lambda lst, item, text: {
            "list_uid": lst,
            "name": "bread",
            "done": False,
            "tags": [],
            "description": text,
            "quantity": 1,
            "completed_at": None,
        },
        DESCRIPTION,
        "Description",
    ),
]


def _send(op_type: str, fields: Fields, text: str) -> dict[str, Any]:
    _, slug = home()
    list_id, list_uid = default_list()
    item_uid = add_item(list_id, "milk")
    body = {"op_id": new_id(), "type": op_type, **fields(list_uid, item_uid, text)}
    return op(client_for(slug), slug, body)


@pytest.mark.parametrize(("op_type", "fields", "limit", "what"), CASES)
def test_text_at_the_limit_is_saved(op_type, fields, limit, what):
    # Lowercase, so item names are stored exactly as sent.
    assert _send(op_type, fields, "x" * limit)["status"] == "applied"


@pytest.mark.parametrize(("op_type", "fields", "limit", "what"), CASES)
def test_text_over_the_limit_is_rejected(op_type, fields, limit, what):
    response = _send(op_type, fields, "x" * (limit + 1))
    assert response["status"] == "rejected"
    assert response["code"] == "too_long"
    assert response["message"] == f"{what} can be at most {limit} characters"


def test_limits_count_characters_after_trimming():
    # Outer spaces are removed before checking; an emoji counts as one.
    assert _send(*CASES[0][:2], f"  {'😀' * NAME}  ")["status"] == "applied"


def test_admin_cannot_create_a_room_with_a_too_long_name(admin_app):
    client = admin(admin_app)
    response = client.post(
        "/api/v1/admin/rooms", json={"name": "x" * (NAME + 1), "password": "pass"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        f"Room name can be at most {NAME} characters"
    )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM rooms WHERE length(name) > ?", (NAME,)
        ).fetchone()[0]
        == 0
    )
