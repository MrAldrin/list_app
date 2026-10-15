from types import SimpleNamespace

import pytest
from api_helpers import (
    create_list,
    get_list_details,
    get_list_details_by_share_token,
    insert_item,
    rename_list,
)

from database_crud import (
    authenticate_room_and_issue_token,
)
from database_setup import db


@pytest.fixture
def shared():
    room_id, room_slug = db.execute("SELECT id, slug FROM rooms").fetchone()
    _, room_token = authenticate_room_and_issue_token(room_slug, "pw")
    list_id, slug = create_list("Secret groceries", room_id)
    return SimpleNamespace(
        room_id=room_id,
        room_slug=room_slug,
        room_token=room_token,
        id=list_id,
        slug=slug,
        token=get_list_details(list_id)["share_token"],
    )


def test_tokens_unique_stable_and_scoped(shared):
    other, _ = create_list("Other", shared.room_id)
    assert len(shared.token) == 43
    assert get_list_details(other)["share_token"] != shared.token
    assert get_list_details_by_share_token(shared.token)["id"] == shared.id
    for invalid in ("", shared.token[:-1], "x" * 43, shared.slug):
        assert get_list_details_by_share_token(invalid) is None
    rename_list(shared.id, "Renamed")
    assert get_list_details_by_share_token(shared.token)["name"] == "Renamed"
    insert_item("Milk", shared.id)
