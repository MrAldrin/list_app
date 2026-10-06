"""Two clients on one room: stale writes, races and interleaved UIs.

The cases follow docs/item-writes.md: a page (or device) can be stale, and
the server must apply intent to the current data, reject stale writes clearly
and keep the changes feed consistent. Each client keeps a copy of the room
built only from the changes feed, as the Svelte data layer will.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from api_helpers import (
    add_item,
    changes,
    client_for,
    home,
    item_row,
    new_id,
    op,
    row_counts,
)
from starlette.testclient import TestClient

import database_crud as crud
from database_setup import db
from item_service import (
    STATUS_ADDED,
    STATUS_RENAMED,
    add_or_restore_item,
    change_item_quantity,
    delete_item_from_list,
    rename_list_with_checks,
    toggle_item_done,
)

TIMEOUT = 30


class Mirror:
    """A client's copy of the room, built only from the changes feed."""

    def __init__(self, client: TestClient, slug: str) -> None:
        self.client = client
        self.slug = slug
        self.since = 0
        self.lists: dict[str, dict] = {}
        self.items: dict[str, dict] = {}

    def sync(self) -> dict[str, Any]:
        feed = changes(self.client, self.slug, self.since)
        if feed["full"]:
            self.lists.clear()
            self.items.clear()
        self.lists.update({row["uid"]: row for row in feed["lists"]})
        self.items.update({row["uid"]: row for row in feed["items"]})
        for deletion in feed["deletions"]:
            target = self.lists if deletion["kind"] == "list" else self.items
            target.pop(deletion["uid"], None)
        # A deleted list takes its items with it (docs/api.md).
        self.items = {
            uid: item
            for uid, item in self.items.items()
            if item["list_uid"] in self.lists
        }
        assert feed["seq"] >= self.since or feed["full"]
        self.since = feed["seq"]
        return feed

    def state(self) -> tuple[dict, dict]:
        return self.lists, self.items

    def item_named(self, name: str) -> dict:
        [item] = [item for item in self.items.values() if item["name"] == name]
        return item

    def write(self, body: dict[str, Any]) -> dict[str, Any]:
        return op(self.client, self.slug, {"op_id": new_id(), **body})


def snapshot(client: TestClient, slug: str) -> tuple[dict, dict]:
    """A fresh full load (since=0)."""
    mirror = Mirror(client, slug)
    assert mirror.sync()["full"]
    return mirror.state()


def db_state(room_id: int) -> tuple[dict, dict]:
    """Lists and items straight from the database, in the feed's terms."""
    lists = {
        uid: (name, slug, changed_seq)
        for uid, name, slug, changed_seq in db.execute(
            "SELECT uid, name, slug, changed_seq FROM lists WHERE room_id = ?",
            (room_id,),
        )
    }
    items = {
        uid: (name, bool(done), quantity, list_uid, changed_seq)
        for uid, name, done, quantity, list_uid, changed_seq in db.execute(
            """
            SELECT items.uid, items.name, items.done, COALESCE(items.quantity, 1),
                   lists.uid, items.changed_seq
            FROM items JOIN lists ON lists.id = items.list_id
            WHERE lists.room_id = ?
            """,
            (room_id,),
        )
    }
    return lists, items


def as_db_terms(state: tuple[dict, dict]) -> tuple[dict, dict]:
    lists, items = state
    return (
        {
            uid: (row["name"], row["slug"], row["changed_seq"])
            for uid, row in lists.items()
        },
        {
            uid: (
                row["name"],
                row["done"],
                row["quantity"],
                row["list_uid"],
                row["changed_seq"],
            )
            for uid, row in items.items()
        },
    )


def assert_consistent(room_id: int, slug: str, *mirrors: Mirror) -> None:
    """Every synced mirror equals a full load, which equals the database."""
    full = snapshot(mirrors[0].client, slug)
    assert as_db_terms(full) == db_state(room_id)
    for mirror in mirrors:
        mirror.sync()
        assert mirror.state() == full


def seq_of(room_id: int) -> int:
    return crud.get_room_seq_locked(room_id)


def groceries() -> tuple[int, str]:
    """(id, uid) of the list made by the `room` fixture."""
    return db.execute("SELECT id, uid FROM lists WHERE name = 'Groceries'").fetchone()


@pytest.fixture
def room() -> tuple[int, str, Mirror, Mirror]:
    """The fixture room with a real list (slug and share link) and two
    signed-in clients, both synced."""
    room_id, slug = home()
    crud.create_list("Groceries", room_id)
    first, second = Mirror(client_for(slug), slug), Mirror(client_for(slug), slug)
    first.sync()
    second.sync()
    return room_id, slug, first, second


def test_each_client_sees_the_others_writes(room):
    room_id, slug, a, b = room
    _, list_uid = groceries()
    added = a.write({"type": "item.add", "list_uid": list_uid, "name": "Milk"})
    b.sync()
    milk = b.item_named("milk")
    assert milk["uid"] == added["result"]["item_uid"]
    b.write(
        {
            "type": "item.set_done",
            "list_uid": list_uid,
            "item_uid": milk["uid"],
            "done": True,
        }
    )
    a.sync()
    assert a.items[milk["uid"]]["done"] is True
    assert_consistent(room_id, slug, a, b)


def test_stale_item_writes_after_the_other_client_deleted_it(room):
    room_id, slug, a, b = room
    list_id, list_uid = groceries()
    item_uid = add_item(list_id, "milk")
    a.sync()
    b.sync()
    a.write({"type": "item.delete", "list_uid": list_uid, "item_uid": item_uid})
    seq = seq_of(room_id)
    counts = row_counts()

    # b still shows the item and acts on it.
    target = {"list_uid": list_uid, "item_uid": item_uid}
    for body in (
        {"type": "item.set_done", "done": True},
        {"type": "item.quantity_delta", "delta": 1},
        {"type": "item.edit", "name": "milk", "description": "x", "base_seq": 1},
        {"type": "item.toggle_tag", "tag": "Lidl"},
    ):
        response = b.write({**body, **target})
        assert response["status"] == "rejected"
        assert response["code"] == "item_not_found"
        assert response["seq"] == seq
    # A repeated delete is not an error, and changes nothing.
    assert b.write({"type": "item.delete", **target})["status"] == "applied"
    assert (seq_of(room_id), row_counts()) == (seq, counts)

    b.sync()
    assert item_uid not in b.items
    assert_consistent(room_id, slug, a, b)


def test_stale_writes_on_a_list_the_other_client_deleted(room):
    room_id, slug, a, b = room
    list_id, list_uid = groceries()
    item_uid = add_item(list_id, "milk")
    a.sync()
    b.sync()
    a.write({"type": "list.delete", "list_uid": list_uid})
    seq = seq_of(room_id)
    counts = row_counts()

    item = {"list_uid": list_uid, "item_uid": item_uid}
    for body in (
        {"type": "item.add", "list_uid": list_uid, "name": "bread"},
        {"type": "item.set_done", "done": True, **item},
        {"type": "item.quantity_delta", "delta": 2, **item},
        {"type": "item.delete", **item},
        {"type": "list.rename", "list_uid": list_uid, "name": "New", "base_seq": 0},
        {"type": "list.tag_add", "list_uid": list_uid, "tag": "Lidl"},
        {"type": "list.visibility", "list_uid": list_uid, "mode": "all"},
        {
            "type": "item.restore",
            "list_uid": list_uid,
            "name": "milk",
            "done": False,
            "tags": [],
            "description": "",
            "quantity": 1,
            "completed_at": None,
        },
    ):
        response = b.write(body)
        assert response["status"] == "rejected", body
        assert response["code"] == "list_unavailable"
        assert response["seq"] == seq
    assert (seq_of(room_id), row_counts()) == (seq, counts)

    b.sync()
    assert list_uid not in b.lists
    assert item_uid not in b.items
    assert_consistent(room_id, slug, a, b)


def test_a_renamed_list_keeps_its_uid(room):
    room_id, slug, a, b = room
    _, list_uid = groceries()
    old_slug = b.lists[list_uid]["slug"]
    a.write(
        {"type": "list.rename", "list_uid": list_uid, "name": "Shop", "base_seq": 0}
    )

    # b has not seen the rename; its ops use the uid, so they still work.
    added = b.write({"type": "item.add", "list_uid": list_uid, "name": "milk"})
    assert added["status"] == "applied"
    b.sync()
    renamed = b.lists[list_uid]
    assert renamed["name"] == "Shop"
    assert renamed["slug"] == old_slug  # a rename keeps the slug (and its URL)
    assert b.items[added["result"]["item_uid"]]["list_uid"] == list_uid
    assert_consistent(room_id, slug, a, b)


def test_a_list_renamed_directly_keeps_its_uid(room):
    room_id, slug, a, b = room
    list_id, list_uid = groceries()
    old_slug = b.lists[list_uid]["slug"]
    status, _ = rename_list_with_checks(
        list_id, room_id, "Shop", expected_slug=old_slug
    )
    assert status == STATUS_RENAMED
    response = b.write({"type": "list.tag_add", "list_uid": list_uid, "tag": "Lidl"})
    assert response["status"] == "applied"
    b.sync()
    assert b.lists[list_uid]["slug"] == old_slug
    assert b.lists[list_uid]["name"] == "Shop"
    assert b.lists[list_uid]["tags"] == ["Lidl"]
    assert_consistent(room_id, slug, a, b)


def test_both_clients_add_the_same_name(room):
    room_id, slug, a, b = room
    _, list_uid = groceries()
    # Neither has seen the other's add.
    first = a.write({"type": "item.add", "list_uid": list_uid, "name": "milk"})
    second = b.write({"type": "item.add", "list_uid": list_uid, "name": "Milk"})
    assert first["status"] == "applied"
    assert second["status"] == "rejected"
    assert second["code"] == "duplicate_active"
    assert second["seq"] == first["seq"]
    b.sync()
    assert [item["name"] for item in b.items.values()] == ["milk"]
    assert_consistent(room_id, slug, a, b)


def run_in_parallel(*jobs) -> list[Any]:
    """Start the jobs together; fail instead of hanging on a deadlock."""
    barrier = threading.Barrier(len(jobs))

    def start(job):
        barrier.wait(TIMEOUT)
        return job()

    with ThreadPoolExecutor(len(jobs)) as pool:
        futures = [pool.submit(start, job) for job in jobs]
        return [future.result(timeout=TIMEOUT) for future in futures]


def test_duplicate_add_race_in_parallel(room):
    room_id, slug, a, b = room
    _, list_uid = groceries()
    for round_number in range(10):
        name = f"item {round_number}"
        results = run_in_parallel(
            lambda: a.write({"type": "item.add", "list_uid": list_uid, "name": name}),
            lambda: b.write({"type": "item.add", "list_uid": list_uid, "name": name}),
        )
        statuses = sorted((result["status"], result.get("code")) for result in results)
        assert statuses == [("applied", None), ("rejected", "duplicate_active")]
    assert len(snapshot(a.client, slug)[1]) == 10
    assert_consistent(room_id, slug, a, b)


def test_quantity_deltas_from_both_clients_add_up(room):
    room_id, slug, a, b = room
    list_id, list_uid = groceries()
    item_uid = add_item(list_id, "milk")
    body = {"type": "item.quantity_delta", "list_uid": list_uid, "item_uid": item_uid}

    def plus(mirror: Mirror, delta: int, times: int):
        return lambda: [mirror.write({**body, "delta": delta}) for _ in range(times)]

    run_in_parallel(plus(a, 1, 20), plus(b, 2, 20))
    assert item_row(item_uid)["quantity"] == 1 + 20 + 40
    assert_consistent(room_id, slug, a, b)


def test_undo_after_the_other_client_re_added_the_name(room):
    room_id, slug, a, b = room
    list_id, list_uid = groceries()
    item_uid = add_item(list_id, "milk", done=True)
    a.sync()
    kept = a.items[item_uid]  # what a keeps for its undo
    a.write({"type": "item.delete", "list_uid": list_uid, "item_uid": item_uid})
    b.write({"type": "item.add", "list_uid": list_uid, "name": "milk"})
    seq = seq_of(room_id)

    undo = a.write(
        {
            "type": "item.restore",
            "list_uid": list_uid,
            "name": kept["name"],
            "done": kept["done"],
            "tags": kept["tags"],
            "description": kept["description"],
            "quantity": kept["quantity"],
            "completed_at": kept["completed_at"],
        }
    )
    assert undo["status"] == "rejected"
    assert undo["code"] == "undo_name_taken"
    assert undo["seq"] == seq
    a.sync()
    [milk] = a.items.values()
    assert milk["uid"] != item_uid
    assert milk["done"] is False
    assert_consistent(room_id, slug, a, b)


def test_direct_and_api_writes_interleaved(room):
    room_id, slug, a, b = room
    list_id, list_uid = groceries()
    list_slug = a.lists[list_uid]["slug"]
    seqs = [seq_of(room_id)]

    def direct(write) -> None:
        write()
        seqs.append(seq_of(room_id))
        assert_consistent(room_id, slug, a, b)

    def api(mirror: Mirror, body: dict[str, Any]) -> None:
        response = mirror.write(body)
        assert response["status"] == "applied", response
        seqs.append(response["seq"])
        assert response["seq"] == seq_of(room_id)
        assert_consistent(room_id, slug, a, b)

    direct(lambda: add_or_restore_item(list_id, "milk", expected_slug=list_slug))
    milk_uid = a.item_named("milk")["uid"]
    milk_id = db.execute("SELECT id FROM items WHERE uid = ?", (milk_uid,)).fetchone()[
        0
    ]
    milk = {"list_uid": list_uid, "item_uid": milk_uid}
    api(a, {"type": "item.quantity_delta", "delta": 2, **milk})
    direct(lambda: change_item_quantity(list_id, milk_id, 1, expected_slug=list_slug))
    api(b, {"type": "item.set_done", "done": True, **milk})
    direct(lambda: toggle_item_done(list_id, milk_id, False, expected_slug=list_slug))
    api(a, {"type": "item.add", "list_uid": list_uid, "name": "bread"})
    direct(lambda: crud.add_list_tag(list_id, "Lidl", expected_slug=list_slug))
    api(b, {"type": "item.toggle_tag", "tag": "Lidl", **milk})
    direct(
        lambda: rename_list_with_checks(
            list_id, room_id, "Shop", expected_slug=list_slug
        )
    )
    list_slug = crud.get_list_details(list_id)["slug"]
    direct(lambda: delete_item_from_list(list_id, milk_id, expected_slug=list_slug))
    api(a, {"type": "item.add", "list_uid": list_uid, "name": "milk"})
    share = crud.get_list_details(list_id)["share_token"]
    direct(lambda: crud.add_item("tea", list_id, expected_slug=f"share:{share}"))

    assert seqs == sorted(set(seqs)), "seq must grow with every write"
    assert a.item_named("milk")["uid"] != milk_uid
    assert {item["name"] for item in a.items.values()} == {"bread", "milk", "tea"}
    assert a.lists[list_uid]["name"] == "Shop"


def test_parallel_requests_keep_seq_and_feed_consistent(room):
    """Two clients and direct database writes at once: no deadlock, no lost seq."""
    room_id, slug, a, b = room
    list_id, list_uid = groceries()
    list_slug = a.lists[list_uid]["slug"]
    shared_uid = add_item(list_id, "shared")
    shared_id = db.execute(
        "SELECT id FROM items WHERE uid = ?", (shared_uid,)
    ).fetchone()[0]
    start_seq = seq_of(room_id)
    rounds = 15

    def client_job(mirror: Mirror, prefix: str):
        def job() -> list[dict]:
            responses = []
            for number in range(rounds):
                responses.append(
                    mirror.write(
                        {
                            "type": "item.add",
                            "list_uid": list_uid,
                            "name": f"{prefix}{number}",
                        }
                    )
                )
                responses.append(
                    mirror.write(
                        {
                            "type": "item.quantity_delta",
                            "list_uid": list_uid,
                            "item_uid": shared_uid,
                            "delta": 1,
                        }
                    )
                )
            return responses

        return job

    def direct_job() -> int:
        for number in range(rounds):
            change_item_quantity(list_id, shared_id, 1, expected_slug=list_slug)
            status, _ = add_or_restore_item(
                list_id, f"n{number}", expected_slug=list_slug
            )
            assert status == STATUS_ADDED
        return 2 * rounds

    from_a, from_b, direct_writes = run_in_parallel(
        client_job(a, "a"), client_job(b, "b"), direct_job
    )

    api_responses = from_a + from_b
    assert all(response["status"] == "applied" for response in api_responses)
    api_seqs = [response["seq"] for response in api_responses]
    # Each applied op bumped the seq on its own: no two share a value.
    assert len(set(api_seqs)) == len(api_seqs)
    for responses in (from_a, from_b):
        own = [response["seq"] for response in responses]
        assert own == sorted(own)
    # Every write bumped exactly once.
    assert seq_of(room_id) == start_seq + len(api_responses) + direct_writes
    assert item_row(shared_uid)["quantity"] == 1 + 3 * rounds
    assert len(snapshot(a.client, slug)[1]) == 1 + 3 * rounds
    assert_consistent(room_id, slug, a, b)
