"""The changes feed of the JSON API (docs/api.md, "Reading: the changes feed")."""

import json
from collections.abc import Callable

import pytest
from starlette.testclient import TestClient

import api.changes
import database_crud as crud
import main
from database_setup import db

HTTPS = "https://testserver"

LIST_KEYS = {"uid", "slug", "name", "tags", "hide_done", "changed_seq"}
ITEM_KEYS = {
    "uid",
    "list_uid",
    "name",
    "done",
    "completed_at",
    "quantity",
    "description",
    "tags",
    "changed_seq",
}


def home() -> tuple[int, str]:
    room_id, slug = db.execute(
        "SELECT id, slug FROM rooms WHERE name = 'Home'"
    ).fetchone()
    return room_id, slug


def signed_in(slug: str, password: str = "pw") -> TestClient:
    client = TestClient(
        main.app,
        base_url=HTTPS,
        headers={"Origin": HTTPS},
        raise_server_exceptions=False,
    )
    response = client.post(f"/api/v1/rooms/{slug}/session", json={"password": password})
    assert response.status_code == 200
    return client


def feed(client: TestClient, slug: str, since: int) -> dict:
    response = client.get(f"/api/v1/rooms/{slug}/changes", params={"since": since})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def uid(table: str, row_id: int) -> str:
    return db.execute(f"SELECT uid FROM {table} WHERE id = ?", (row_id,)).fetchone()[0]


def room_seq(room_id: int) -> int:
    return crud.get_room_seq_locked(room_id)


def item_id(list_id: int, name: str) -> int:
    return db.execute(
        "SELECT id FROM items WHERE list_id = ? AND name = ?", (list_id, name)
    ).fetchone()[0]


def by_uid(rows: list[dict]) -> dict[str, dict]:
    return {row["uid"]: row for row in rows}


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.headers["cache-control"] == "no-store"


@pytest.fixture
def shop() -> tuple[int, int, str]:
    """Home room with a "Shop" list holding milk (open) and bread (done)."""
    room_id, slug = home()
    list_id, _ = crud.create_list("Shop", room_id)
    crud.add_item("milk", list_id)
    crud.add_item("bread", list_id)
    crud.update_item_done(item_id(list_id, "bread"), list_id, True)
    return room_id, list_id, slug


def test_full_snapshot(shop):
    room_id, list_id, slug = shop
    crud.add_list_tag(list_id, "market")
    crud.add_list_tag(list_id, "Lidl")
    crud.add_list_tag(list_id, "aldi")
    crud.update_list_visibility_settings(
        list_id, mode="age", age_days=3, recent_count=5
    )
    milk = item_id(list_id, "milk")
    crud.update_item_details(milk, list_id, "milk", "lactose free", 2)
    crud.toggle_item_active_tag(milk, list_id, "market")
    crud.toggle_item_active_tag(milk, list_id, "aldi")

    data = feed(signed_in(slug), slug, 0)

    assert set(data) == {"seq", "full", "room", "lists", "items", "deletions"}
    assert data["full"] is True
    assert data["seq"] == room_seq(room_id)
    assert data["room"] == {"slug": slug, "name": "Home"}
    assert data["deletions"] == []
    lists = by_uid(data["lists"])
    assert len(lists) == 2  # "default" from the test setup, and "Shop"
    shop_list = lists[uid("lists", list_id)]
    assert set(shop_list) == LIST_KEYS
    details = crud.get_list_details(list_id)
    assert shop_list == {
        "uid": uid("lists", list_id),
        "slug": details["slug"],
        "name": "Shop",
        "tags": ["aldi", "Lidl", "market"],
        "hide_done": {"mode": "age", "age_days": 3, "recent_count": 5},
        "changed_seq": db.execute(
            "SELECT changed_seq FROM lists WHERE id = ?", (list_id,)
        ).fetchone()[0],
    }

    items = by_uid(data["items"])
    assert len(items) == 2
    milk_row = items[uid("items", milk)]
    assert set(milk_row) == ITEM_KEYS
    assert milk_row["list_uid"] == shop_list["uid"]
    assert milk_row["name"] == "milk"
    assert milk_row["done"] is False
    assert milk_row["completed_at"] is None
    assert milk_row["quantity"] == 2
    assert milk_row["description"] == "lactose free"
    assert milk_row["tags"] == ["market", "aldi"]  # item tags keep their order
    bread_row = items[uid("items", item_id(list_id, "bread"))]
    assert bread_row["done"] is True
    assert bread_row["completed_at"].endswith("Z")
    assert bread_row["quantity"] == 1
    assert bread_row["description"] == ""
    assert bread_row["tags"] == []
    # seq and every row come from the same moment.
    assert data["seq"] == max(
        row["changed_seq"] for row in data["items"] + data["lists"]
    )


def test_odd_stored_values_are_read_leniently(shop):
    _, list_id, slug = shop
    milk = item_id(list_id, "milk")
    bread = item_id(list_id, "bread")
    db.execute(
        "UPDATE items SET quantity = NULL, description = NULL, active_tags = 'oops', "
        "completed_at = '2026-10-03T11:12:44+02:00' WHERE id = ?",
        (milk,),
    )
    db.execute(
        "UPDATE items SET active_tags = '{\"a\": 1}', completed_at = 'yesterday' "
        "WHERE id = ?",
        (bread,),
    )
    db.execute(
        'UPDATE lists SET list_tags = \'["b", 3, "A"]\' WHERE id = ?', (list_id,)
    )
    db.commit()

    data = feed(signed_in(slug), slug, 0)
    items = by_uid(data["items"])
    milk_row = items[uid("items", milk)]
    assert milk_row["quantity"] == 1
    assert milk_row["description"] == ""
    assert milk_row["tags"] == []
    # Not done: no completion time, whatever is stored.
    assert milk_row["completed_at"] is None
    bread_row = items[uid("items", bread)]
    assert bread_row["tags"] == []
    assert bread_row["completed_at"] is None  # unreadable time
    assert by_uid(data["lists"])[uid("lists", list_id)]["tags"] == ["A", "b"]


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("2026-10-03T09:12:44.123456Z", "2026-10-03T09:12:44.123456Z"),
        ("2026-10-03T11:12:44+02:00", "2026-10-03T09:12:44.000000Z"),
        ("2026-10-03T09:12:44", "2026-10-03T09:12:44.000000Z"),  # naive = UTC
        ("not a time", None),
        (None, None),
    ],
)
def test_completed_at_is_utc_with_z(shop, stored, expected):
    _, list_id, slug = shop
    bread = item_id(list_id, "bread")
    db.execute("UPDATE items SET completed_at = ? WHERE id = ?", (stored, bread))
    db.commit()
    items = by_uid(feed(signed_in(slug), slug, 0)["items"])
    assert items[uid("items", bread)]["completed_at"] == expected


def _rename_list(room_id: int, list_id: int) -> None:
    crud.rename_list(list_id, "Market")


def _add_list_tag(room_id: int, list_id: int) -> None:
    crud.add_list_tag(list_id, "Lidl")


def _visibility(room_id: int, list_id: int) -> None:
    crud.update_list_visibility_settings(
        list_id, mode="recent", age_days=7, recent_count=3
    )


def _check_milk(room_id: int, list_id: int) -> None:
    crud.update_item_done(item_id(list_id, "milk"), list_id, True)


def _restore_bread(room_id: int, list_id: int) -> None:
    assert crud.add_or_restore_item_atomic("bread", list_id) == "restored"


def _quantity(room_id: int, list_id: int) -> None:
    crud.adjust_item_quantity(item_id(list_id, "milk"), list_id, 2)


def _details(room_id: int, list_id: int) -> None:
    crud.update_item_details(item_id(list_id, "milk"), list_id, "oat milk", "x")


def _item_tag(room_id: int, list_id: int) -> None:
    crud.toggle_item_active_tag(item_id(list_id, "milk"), list_id, "Lidl")


@pytest.mark.parametrize(
    ("write", "changed"),
    [
        (_rename_list, "list"),
        (_add_list_tag, "list"),
        (_visibility, "list"),
        (_check_milk, "milk"),
        (_restore_bread, "bread"),
        (_quantity, "milk"),
        (_details, "milk"),
        (_item_tag, "milk"),
    ],
)
def test_delta_after_each_kind_of_write(
    shop, write: Callable[[int, int], None], changed: str
):
    room_id, list_id, slug = shop
    milk_uid = uid("items", item_id(list_id, "milk"))
    bread_uid = uid("items", item_id(list_id, "bread"))
    client = signed_in(slug)
    before = feed(client, slug, 0)["seq"]

    write(room_id, list_id)

    data = feed(client, slug, before)
    assert data["full"] is False
    assert data["seq"] == room_seq(room_id) == before + 1
    assert data["deletions"] == []
    if changed == "list":
        assert [row["uid"] for row in data["lists"]] == [uid("lists", list_id)]
        assert data["items"] == []
    else:
        expected = milk_uid if changed == "milk" else bread_uid
        assert data["lists"] == []
        assert [row["uid"] for row in data["items"]] == [expected]
        assert data["items"][0]["changed_seq"] == data["seq"]
    # Nothing new after the latest seq.
    latest = feed(client, slug, data["seq"])
    assert (latest["lists"], latest["items"], latest["deletions"]) == ([], [], [])


def test_delta_shows_new_list_and_item(shop):
    room_id, _, slug = shop
    client = signed_in(slug)
    before = feed(client, slug, 0)["seq"]
    new_list_id, _ = crud.create_list("Hardware", room_id)
    crud.add_item("nails", new_list_id)
    data = feed(client, slug, before)
    assert [row["name"] for row in data["lists"]] == ["Hardware"]
    assert [row["name"] for row in data["items"]] == ["nails"]
    assert data["items"][0]["list_uid"] == uid("lists", new_list_id)


def test_room_rename_shows_in_the_feed(shop):
    room_id, _, slug = shop
    client = signed_in(slug)
    before = feed(client, slug, 0)["seq"]
    crud.rename_room(room_id, "Cabin")
    data = feed(client, slug, before)
    assert data["room"] == {"slug": slug, "name": "Cabin"}
    assert data["seq"] == before + 1
    assert (data["lists"], data["items"], data["deletions"]) == ([], [], [])


def test_item_deletion(shop):
    _, list_id, slug = shop
    client = signed_in(slug)
    before = feed(client, slug, 0)["seq"]
    milk = item_id(list_id, "milk")
    milk_uid = uid("items", milk)
    crud.delete_item(milk, list_id)
    data = feed(client, slug, before)
    assert data["deletions"] == [{"kind": "item", "uid": milk_uid}]
    assert data["items"] == [] and data["lists"] == []
    # A full snapshot has no deletions and no deleted rows.
    full = feed(client, slug, 0)
    assert full["deletions"] == []
    assert milk_uid not in by_uid(full["items"])


def test_list_deletion_with_items(shop):
    _, list_id, slug = shop
    client = signed_in(slug)
    before = feed(client, slug, 0)["seq"]
    list_uid = uid("lists", list_id)
    item_uids = {uid("items", item_id(list_id, name)) for name in ("milk", "bread")}
    crud.delete_list(list_id)
    data = feed(client, slug, before)
    assert data["lists"] == [] and data["items"] == []
    assert data["deletions"][-1] == {"kind": "list", "uid": list_uid}
    assert {row["uid"] for row in data["deletions"][:-1]} == item_uids
    assert {row["kind"] for row in data["deletions"][:-1]} == {"item"}
    full = feed(client, slug, 0)
    assert list_uid not in by_uid(full["lists"])
    assert not item_uids & set(by_uid(full["items"]))


def test_list_created_and_deleted_after_since_is_only_a_deletion(shop):
    room_id, _, slug = shop
    client = signed_in(slug)
    before = feed(client, slug, 0)["seq"]
    temp_id, _ = crud.create_list("Temp", room_id)
    crud.add_item("thing", temp_id)
    temp_uid = uid("lists", temp_id)
    crud.delete_list(temp_id)
    data = feed(client, slug, before)
    assert data["lists"] == [] and data["items"] == []
    assert {"kind": "list", "uid": temp_uid} in data["deletions"]


def test_since_ahead_of_the_server_gives_a_full_snapshot(shop):
    room_id, list_id, slug = shop
    client = signed_in(slug)
    crud.delete_item(item_id(list_id, "milk"), list_id)
    seq = room_seq(room_id)
    data = feed(client, slug, seq + 10)
    assert data["full"] is True
    assert data["seq"] == seq
    assert data["deletions"] == []
    assert len(data["lists"]) == 2 and len(data["items"]) == 1


def test_other_rooms_never_leak(shop):
    room_id, _, slug = shop
    other_id, other_slug = crud.create_room("Other", "other-pw")
    other_list, _ = crud.create_list("Secret", other_id)
    crud.add_item("hidden", other_list)
    crud.add_item("gone", other_list)
    client = signed_in(slug)
    before = feed(client, slug, 0)["seq"]
    crud.delete_item(item_id(other_list, "gone"), other_list)
    crud.update_item_done(item_id(other_list, "hidden"), other_list, True)
    crud.rename_list(other_list, "Secret 2")

    full = feed(client, slug, 0)
    delta = feed(client, slug, before)
    other_uids = {uid("lists", other_list), uid("items", item_id(other_list, "hidden"))}
    for data in (full, delta):
        uids = {row["uid"] for row in data["lists"] + data["items"] + data["deletions"]}
        assert not uids & other_uids
        assert "Secret" not in json.dumps(data) and "hidden" not in json.dumps(data)
    assert delta["seq"] == before == room_seq(room_id)
    assert delta["deletions"] == []
    # And the other room sees only its own data.
    other = feed(signed_in(other_slug, "other-pw"), other_slug, 0)
    assert [row["name"] for row in other["lists"]] == ["Secret 2"]
    assert [row["name"] for row in other["items"]] == ["hidden"]


def test_no_access_and_unknown_room_look_the_same(shop):
    _, _, slug = shop
    _, other_slug = crud.create_room("Other", "other-pw")
    stranger = TestClient(main.app, base_url=HTTPS, raise_server_exceptions=False)
    no_cookie = stranger.get(f"/api/v1/rooms/{slug}/changes?since=0")
    unknown = stranger.get("/api/v1/rooms/no-such-room/changes?since=0")
    other_room_cookie = signed_in(other_slug, "other-pw").get(
        f"/api/v1/rooms/{slug}/changes?since=0"
    )
    for response in (no_cookie, unknown, other_room_cookie):
        assert_error(response, 401, "not_authenticated")
    assert no_cookie.content == unknown.content == other_room_cookie.content


def test_revoked_token_is_401(shop):
    _, _, slug = shop
    client = signed_in(slug)
    token = next(iter(client.cookies.values()))
    crud.revoke_room_access_token(slug, token)
    assert_error(
        client.get(f"/api/v1/rooms/{slug}/changes?since=0"), 401, "not_authenticated"
    )


def test_password_change_revokes_feed_access(shop):
    room_id, _, slug = shop
    client = signed_in(slug)
    crud.update_room_password(room_id, "new-password")
    assert_error(
        client.get(f"/api/v1/rooms/{slug}/changes?since=0"), 401, "not_authenticated"
    )


@pytest.mark.parametrize(
    "query", ["", "?since=", "?since=-1", "?since=abc", "?since=1.5", f"?since={2**63}"]
)
def test_bad_since_is_422(shop, query):
    _, _, slug = shop
    response = signed_in(slug).get(f"/api/v1/rooms/{slug}/changes{query}")
    assert_error(response, 422, "invalid_request")


def test_no_integer_ids_or_secrets_in_the_feed(shop):
    room_id, _, slug = shop
    data = feed(signed_in(slug), slug, 0)
    text = json.dumps(data)
    for row in data["lists"] + data["items"]:
        assert "id" not in row
    share_tokens = [
        row[0]
        for row in db.execute(
            "SELECT share_token FROM lists WHERE share_token IS NOT NULL"
        )
    ]
    assert share_tokens
    password_hash = db.execute(
        "SELECT password_hash FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]
    for secret in [*share_tokens, password_hash]:
        assert secret not in text
    assert "share" not in text and "password" not in text


def test_feed_reads_in_one_access_transaction(shop, monkeypatch):
    _, _, slug = shop
    seen = []
    original = api.changes.get_item_changes_locked

    def spy(room_id: int, since: int | None) -> list[dict]:
        seen.append(db.in_transaction)
        return original(room_id, since)

    monkeypatch.setattr(api.changes, "get_item_changes_locked", spy)
    feed(signed_in(slug), slug, 0)
    assert seen == [True]
