"""Retry-safe writes for every op type (docs/api.md, "Writing: operations").

Each op type has an applied and a rejected case. A replay must return the
stored bytes without writing or notifying again; HTTP errors are not stored.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from api_helpers import (
    add_item,
    assert_error,
    client_for,
    default_list,
    home,
    new_id,
    processed_ops_count,
    row_counts,
    send,
)
from starlette.testclient import TestClient

import api.ops
import database_crud as crud
import live_updates
from database_setup import db


@dataclass
class Ctx:
    room_id: int
    slug: str
    list_uid: str
    milk_uid: str


Body = Callable[[Ctx], dict[str, Any]]


@dataclass
class Case:
    type: str
    status: str  # "applied" or "rejected"
    fields: Body
    code: str | None = None

    @property
    def id(self) -> str:
        return f"{self.type}-{self.code or self.status}"


def applied(op_type: str, fields: Body) -> Case:
    return Case(op_type, "applied", fields)


def rejected(op_type: str, code: str, fields: Body) -> Case:
    return Case(op_type, "rejected", fields, code)


RESTORE = {
    "done": False,
    "tags": [],
    "description": "",
    "quantity": 1,
    "completed_at": None,
}

CASES = [
    applied("list.create", lambda c: {"name": "Market"}),
    rejected("list.create", "invalid_name", lambda c: {"name": " "}),
    applied(
        "list.rename",
        lambda c: {"list_uid": c.list_uid, "name": "Groceries", "base_seq": 0},
    ),
    rejected(
        "list.rename",
        "duplicate_name",
        lambda c: {"list_uid": c.list_uid, "name": "shop", "base_seq": 0},
    ),
    applied("list.delete", lambda c: {"list_uid": c.list_uid}),
    rejected("list.delete", "list_unavailable", lambda c: {"list_uid": new_id()}),
    applied("list.tag_add", lambda c: {"list_uid": c.list_uid, "tag": "Market"}),
    rejected(
        "list.tag_add", "invalid_name", lambda c: {"list_uid": c.list_uid, "tag": ""}
    ),
    applied("list.tag_remove", lambda c: {"list_uid": c.list_uid, "tag": "Lidl"}),
    rejected(
        "list.tag_remove",
        "list_unavailable",
        lambda c: {"list_uid": new_id(), "tag": "Lidl"},
    ),
    applied("list.visibility", lambda c: {"list_uid": c.list_uid, "mode": "all"}),
    rejected(
        "list.visibility",
        "list_unavailable",
        lambda c: {"list_uid": new_id(), "age_days": 3},
    ),
    applied("item.add", lambda c: {"list_uid": c.list_uid, "name": "eggs"}),
    rejected(
        "item.add",
        "duplicate_active",
        lambda c: {"list_uid": c.list_uid, "name": "milk"},
    ),
    applied(
        "item.set_done",
        lambda c: {"list_uid": c.list_uid, "item_uid": c.milk_uid, "done": True},
    ),
    rejected(
        "item.set_done",
        "item_not_found",
        lambda c: {"list_uid": c.list_uid, "item_uid": new_id(), "done": True},
    ),
    applied(
        "item.quantity_delta",
        lambda c: {"list_uid": c.list_uid, "item_uid": c.milk_uid, "delta": 1},
    ),
    rejected(
        "item.quantity_delta",
        "item_not_found",
        lambda c: {"list_uid": c.list_uid, "item_uid": new_id(), "delta": 1},
    ),
    applied(
        "item.edit",
        lambda c: {
            "list_uid": c.list_uid,
            "item_uid": c.milk_uid,
            "name": "oat milk",
            "description": "",
            "base_seq": 0,
        },
    ),
    rejected(
        "item.edit",
        "duplicate_name",
        lambda c: {
            "list_uid": c.list_uid,
            "item_uid": c.milk_uid,
            "name": "bread",
            "description": "",
            "base_seq": 0,
        },
    ),
    applied(
        "item.toggle_tag",
        lambda c: {"list_uid": c.list_uid, "item_uid": c.milk_uid, "tag": "Lidl"},
    ),
    rejected(
        "item.toggle_tag",
        "item_not_found",
        lambda c: {"list_uid": c.list_uid, "item_uid": new_id(), "tag": "Lidl"},
    ),
    applied("item.delete", lambda c: {"list_uid": c.list_uid, "item_uid": c.milk_uid}),
    rejected(
        "item.delete",
        "list_unavailable",
        lambda c: {"list_uid": new_id(), "item_uid": c.milk_uid},
    ),
    applied(
        "item.restore", lambda c: {"list_uid": c.list_uid, "name": "eggs", **RESTORE}
    ),
    rejected(
        "item.restore",
        "undo_name_taken",
        lambda c: {"list_uid": c.list_uid, "name": "milk", **RESTORE},
    ),
]

TYPES = sorted({case.type for case in CASES})


def test_every_op_type_has_an_applied_and_a_rejected_case():
    assert set(TYPES) == set(api.ops.HANDLERS)
    for status in ("applied", "rejected"):
        assert {case.type for case in CASES if case.status == status} == set(TYPES)


@pytest.fixture
def ctx() -> Ctx:
    """The default list with a tag, an open 'milk', a checked 'bread', and
    another list 'shop'."""
    room_id, slug = home()
    list_id, list_uid = default_list()
    crud.add_list_tag(list_id, "Lidl")
    milk_uid = add_item(list_id, "milk")
    add_item(list_id, "bread", done=True)
    crud.create_list("shop", room_id)
    return Ctx(room_id, slug, list_uid, milk_uid)


@pytest.fixture
def client(ctx: Ctx) -> TestClient:
    return client_for(ctx.slug)


@pytest.fixture
def notified(monkeypatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(live_updates, "_listeners", [calls.append])
    return calls


def body_for(case: Case, ctx: Ctx, op_id: str | None = None) -> dict[str, Any]:
    return {"op_id": op_id or new_id(), "type": case.type, **case.fields(ctx)}


def snapshot(room_id: int) -> tuple:
    """Everything an op could write, plus the room seq."""
    return (
        crud.get_room_seq_locked(room_id),
        row_counts(),
        db.execute("SELECT * FROM lists ORDER BY id").fetchall(),
        db.execute("SELECT * FROM items ORDER BY id").fetchall(),
        db.execute("SELECT * FROM deletions ORDER BY id").fetchall(),
        processed_ops_count(),
    )


def first_send(case: Case, ctx: Ctx, client: TestClient, body: dict) -> bytes:
    response = send(client, ctx.slug, body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == case.status
    assert data.get("code") == case.code
    return response.content


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_replay_returns_the_stored_bytes_without_a_second_write(
    ctx, client, notified, case
):
    body = body_for(case, ctx)
    first = first_send(case, ctx, client, body)
    after_first = snapshot(ctx.room_id)
    expected_notified = [ctx.room_id] if case.status == "applied" else []
    assert notified == expected_notified

    for _ in range(2):
        replay = send(client, ctx.slug, body)
        assert replay.status_code == 200
        assert replay.content == first
    assert snapshot(ctx.room_id) == after_first
    assert notified == expected_notified


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_same_op_id_with_another_body_is_409(ctx, client, notified, case):
    body = body_for(case, ctx)
    first_send(case, ctx, client, body)
    before = snapshot(ctx.room_id)
    calls = list(notified)
    same_type = dict(body)
    if "list_uid" in same_type:
        same_type["list_uid"] = new_id()
    else:
        same_type["name"] = "Something else"
    other_type = {"op_id": body["op_id"], "type": "list.create", "name": "Other"}
    if case.type == "list.create":
        other_type = {
            "op_id": body["op_id"],
            "type": "list.delete",
            "list_uid": ctx.list_uid,
        }
    for changed in (same_type, other_type):
        assert_error(send(client, ctx.slug, changed), 409, "op_id_reused")
    assert snapshot(ctx.room_id) == before
    assert notified == calls


@pytest.mark.parametrize("op_type", TYPES)
def test_same_op_id_in_another_room_is_409(ctx, client, notified, op_type):
    case = next(c for c in CASES if c.type == op_type and c.status == "applied")
    body = body_for(case, ctx)
    first_send(case, ctx, client, body)
    other_id, other_slug = crud.create_room("Other", "other-pw")
    other = client_for(other_slug, "other-pw")
    before = (snapshot(ctx.room_id), crud.get_room_seq_locked(other_id))
    calls = list(notified)
    assert_error(send(other, other_slug, body), 409, "op_id_reused")
    assert (snapshot(ctx.room_id), crud.get_room_seq_locked(other_id)) == before
    assert notified == calls


def _no_cookie(ctx: Ctx, client: TestClient, body: dict):
    return send(client_for(), ctx.slug, body), 401, "not_authenticated"


def _cross_origin(ctx: Ctx, client: TestClient, body: dict):
    response = client.post(
        f"/api/v1/rooms/{ctx.slug}/ops",
        json=body,
        headers={"Origin": "https://evil.example"},
    )
    return response, 403, "forbidden_origin"


def _not_json(ctx: Ctx, client: TestClient, body: dict):
    response = client.post(
        f"/api/v1/rooms/{ctx.slug}/ops",
        content=b"{}",
        headers={"Content-Type": "text/plain"},
    )
    return response, 415, "invalid_request"


def _bad_body(ctx: Ctx, client: TestClient, body: dict):
    return send(client, ctx.slug, body | {"extra": 1}), 422, "invalid_request"


@pytest.mark.parametrize(
    "http_error", [_no_cookie, _cross_origin, _not_json, _bad_body]
)
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_http_errors_are_not_stored(ctx, client, notified, case, http_error):
    body = body_for(case, ctx)
    before = snapshot(ctx.room_id)
    response, status, code = http_error(ctx, client, body)
    assert_error(response, status, code)
    assert snapshot(ctx.room_id) == before
    assert notified == []
    # A later valid request with the same op_id runs normally.
    first_send(case, ctx, client, body)
    assert processed_ops_count() == 1


# Pruning


def _age_op(op_id: str, age: str) -> None:
    db.execute(
        "UPDATE processed_ops SET created_at = "
        "strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?) WHERE op_id = ?",
        (age, op_id),
    )
    db.commit()


def test_pruning_removes_only_entries_older_than_30_days(ctx, client):
    # 30 days = 43,200 minutes; one minute on each side of the cutoff.
    ages = {"old": "-43201 minutes", "edge": "-43199 minutes", "new": "-1 minutes"}
    op_ids = {}
    for name, age in ages.items():
        body = {"op_id": new_id(), "type": "list.create", "name": name}
        assert send(client, ctx.slug, body).status_code == 200
        _age_op(body["op_id"], age)
        op_ids[name] = body["op_id"]

    assert crud.prune_processed_ops() == 1
    kept = {row[0] for row in db.execute("SELECT op_id FROM processed_ops")}
    assert kept == {op_ids["edge"], op_ids["new"]}


def test_a_pruned_op_id_runs_again_as_a_new_op(ctx, client):
    body = {
        "op_id": new_id(),
        "type": "item.add",
        "list_uid": ctx.list_uid,
        "name": "x",
    }
    first = send(client, ctx.slug, body).json()
    assert first["result"]["outcome"] == "added"
    _age_op(body["op_id"], "-31 days")
    crud.prune_processed_ops()
    again = send(client, ctx.slug, body).json()
    assert again["status"] == "rejected"
    assert again["code"] == "duplicate_active"
