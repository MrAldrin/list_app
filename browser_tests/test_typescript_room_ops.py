"""Room operations over HTTP. Both servers use disposable databases only."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2 as httpx
import pytest

from conftest import TestServer, TypeScriptTestServer

pytestmark = pytest.mark.own_server


@pytest.fixture(autouse=True)
def typescript_only(pytestconfig: pytest.Config) -> None:
    if pytestconfig.getoption("--browser-backend") != "typescript":
        pytest.skip("Build and select the TypeScript backend")


@contextmanager
def member(server: TestServer) -> Iterator[httpx.Client]:
    [(slug,)] = server.query("SELECT slug FROM rooms")
    with httpx.Client(base_url=server.url, headers={"Origin": server.url}) as client:
        response = client.post(
            f"/api/v1/rooms/{slug}/session",
            json={"password": server.password},
        )
        response.raise_for_status()
        yield client


def op(kind: str, **fields: Any) -> dict[str, Any]:
    return {"type": kind, "op_id": str(uuid4()), **fields}


def answer(client: httpx.Client, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def reused(client: httpx.Client, path: str, body: dict[str, Any]) -> None:
    response = client.post(path, json=body)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "op_id_reused"


def copy_db(source: TestServer, target: TestServer) -> None:
    with (
        closing(sqlite3.connect(source.database)) as original,
        closing(sqlite3.connect(target.database)) as copy,
    ):
        original.backup(copy)


def test_python_carryover_and_rollback(tmp_path: Path) -> None:
    # obligation: rule-success.ReplaySameOp
    # obligation: rule-success.RefuseReusedOpId
    for sub in ("python", "bun", "rollback"):
        (tmp_path / sub).mkdir()
    reference, bun, rollback = (
        TestServer(tmp_path / "python"),
        TypeScriptTestServer(tmp_path / "bun"),
        TestServer(tmp_path / "rollback"),
    )
    try:
        reference.start()
        path = f"/api/v1/rooms/{reference.room_slug}/ops"
        legacy = op("room.rename", name="Kitchen")
        with member(reference) as client:
            response = answer(client, path, legacy)
            assert response["status"] == "applied"
            assert answer(client, path, dict(reversed(legacy.items()))) == response
            # Python erased the spelling of even the only required UUID.
            assert (
                answer(
                    client, path, legacy | {"op_id": legacy["op_id"].replace("-", "")}
                )
                == response
            )
        copy_db(reference, bun)
        with closing(sqlite3.connect(bun.database)) as db, db:
            db.execute(
                "INSERT INTO processed_ops(op_id, room_id, request_hash,response_json,created_at) SELECT ?,room_id,request_hash,response_json,'2000-01-01' FROM processed_ops",
                (str(uuid4()),),
            )
        bun.start()
        old_rows = reference.query("SELECT * FROM processed_ops")
        assert bun.query("SELECT * FROM processed_ops") == old_rows
        with member(bun) as client:
            reused(client, path, legacy)
            assert bun.query("SELECT * FROM processed_ops") == old_rows
            # Small common-case reference: both apply and replay without another rename.
            new = op("room.rename", name="Pantry")
            with member(reference) as py:
                expected = answer(py, path, new)
                assert answer(py, path, new) == expected
            assert answer(client, path, new) == expected
            assert answer(client, path, new) == expected
            reused(client, path, new | {"op_id": new["op_id"].replace("-", "")})
            create = answer(client, path, op("list.create", name="L"))
            list_uid = create["result"]["list_uid"]
            item = answer(client, path, op("item.add", name="x", list_uid=list_uid))
            delta = op(
                "item.quantity_delta",
                list_uid=list_uid,
                item_uid=item["result"]["item_uid"],
                delta=4,
            )
            assert answer(client, path, delta)["status"] == "applied"
        copy_db(bun, rollback)
        rollback.start()
        with member(rollback) as client:
            reused(client, path, delta)
            assert rollback.query("SELECT quantity FROM items") == [(5,)]
        assert rollback.query(
            "SELECT * FROM processed_ops ORDER BY op_id"
        ) == bun.query("SELECT * FROM processed_ops ORDER BY op_id")
    finally:
        rollback.stop()
        bun.stop()
        reference.stop()


@pytest.mark.parametrize("version", [None, "17.0.0"])
def test_unsupported_name_key_version_stops_before_writes(
    server: TypeScriptTestServer, version: str | None
) -> None:
    server.stop()
    with closing(sqlite3.connect(server.database)) as db, db:
        if version is None:
            db.execute("DELETE FROM item_name_key_metadata")
        else:
            db.execute(
                "UPDATE item_name_key_metadata SET unicode_version=?", (version,)
            )
        db.execute(
            "INSERT INTO processed_ops(op_id,room_id,request_hash,response_json,created_at) SELECT ?,id,'legacy','{}','2000-01-01' FROM rooms",
            (str(uuid4()),),
        )
    stored = server.query("SELECT * FROM processed_ops")
    with pytest.raises(RuntimeError, match="Unsupported item-name key version"):
        server.start()
    assert server.query("SELECT * FROM processed_ops") == stored


def test_item_changes_and_exact_sent_fields(server: TypeScriptTestServer) -> None:
    # obligation: rule-success.FirstOp
    # obligation: rule-entity-creation.FirstOp.1
    path = f"/api/v1/rooms/{server.room_slug}/ops"
    with member(server) as client:
        new_list = op("list.create", name="Straße")
        list_uid = answer(client, path, new_list)["result"]["list_uid"]
        assert (
            answer(client, path, op("list.create", name="STRASSE"))["result"]["created"]
            is False
        )
        # Unicode 15.1 preserves U+1C89. Final sigma ignores combining marks.
        a = answer(
            client,
            path,
            op(
                "item.add",
                list_uid=list_uid,
                name="\u0085\u1c89\u039f\u03a3\u0301\u001f",
            ),
        )["result"]
        assert server.query("SELECT name_key FROM items") == [
            ("\u1c89\u03bf\u03c2\u0301",)
        ]
        uid = a["item_uid"]
        target = {"list_uid": list_uid, "item_uid": uid}
        edit = op(
            "item.edit",
            **target,
            name="Rice",
            description="",
            base_seq=a["changed_seq"],
        )
        # HTTP errors are not admitted and must not consume an ID.
        invalid = edit | {"base_seq": -1}
        assert client.post(path, json=invalid).status_code == 422
        assert (
            client.post(
                path, json=edit, headers={"Origin": "https://elsewhere.test"}
            ).status_code
            == 403
        )
        assert not server.query(
            "SELECT 1 FROM processed_ops WHERE op_id=?", (edit["op_id"],)
        )
        saved = answer(client, path, edit)
        assert saved["status"] == "applied"
        assert answer(client, path, dict(reversed(edit.items()))) == saved
        for field in ("date", "due_time", "due_timezone", "quantity"):
            reused(client, path, edit | {field: None})
        assert server.query("SELECT changed_seq FROM items") == [
            (saved["result"]["changed_seq"],)
        ]
        for day, time, instant in [
            ("2026-03-29", "02:15", "2026-03-29T01:00:00.000Z"),
            ("2026-10-25", "02:15", "2026-10-25T00:15:00.000Z"),
        ]:
            timed = op(
                "item.edit",
                **target,
                name="Rice",
                description="",
                base_seq=saved["seq"],
                date=day,
                due_time=time,
                due_timezone="Europe/Oslo",
            )
            saved = answer(client, path, timed)
            assert saved["status"] == "applied"
            assert server.query("SELECT due_at FROM items") == [(instant,)]
        bad = op(
            "item.edit",
            **target,
            name="Broken",
            description="",
            base_seq=saved["seq"],
            due_timezone="Unknown/Zone",
        )
        rejection = answer(client, path, bad)
        assert rejection["code"] == "time_zone_unavailable"
        assert answer(client, path, bad) == rejection
        assert server.query("SELECT name,changed_seq FROM items") == [
            ("Rice", saved["seq"])
        ]
        check = op("item.set_done", **target, done=True)
        checked = answer(client, path, check)
        assert (
            answer(client, path, op("item.set_done", **target, done=True, base_seq=0))[
                "seq"
            ]
            == checked["seq"]
        )
        assert (
            answer(client, path, op("item.add", list_uid=list_uid, name="rICE"))[
                "result"
            ]["outcome"]
            == "restored"
        )
        duplicate = op("item.add", list_uid=list_uid, name="rice")
        rejected = answer(client, path, duplicate)
        assert rejected["code"] == "duplicate_active" and rejected["item_uid"] == uid
        deleted = answer(client, path, op("item.delete", **target))
        assert deleted["status"] == "applied"
        assert (
            answer(client, path, op("item.delete", **target))["seq"] == deleted["seq"]
        )
        assert answer(client, path, duplicate) == rejected
        restored = answer(
            client,
            path,
            op(
                "item.restore",
                list_uid=list_uid,
                name="Rice",
                description="",
                quantity=2,
                done=False,
                tags=[],
                completed_at=None,
                add_count=2,
                added_at="2026-01-01T10:00:00Z",
            ),
        )
        assert restored["result"]["item_uid"] != uid
        assert server.query("SELECT add_count,added_at FROM items") == [
            (2, "2026-01-01T10:00:00.000Z")
        ]
        assert (
            answer(
                client,
                path,
                op(
                    "list.rename",
                    list_uid=list_uid,
                    name="New",
                    base_seq=restored["seq"],
                ),
            )["status"]
            == "applied"
        )
        assert (
            answer(client, path, op("list.delete", list_uid=list_uid))["status"]
            == "applied"
        )
        assert server.query("SELECT COUNT(*) FROM deletions") == [(3,)]
        assert answer(client, path, duplicate) == rejected
        with httpx.Client(
            base_url=server.url, headers={"Origin": server.url}
        ) as stranger:
            assert stranger.post(path, json=duplicate).status_code == 401
