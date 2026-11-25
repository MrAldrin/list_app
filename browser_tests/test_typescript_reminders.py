"""Private reminder obligations over Bun HTTP on disposable SQLite data."""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2 as httpx
import pytest
from test_typescript_room_access import (
    assert_error,
    assert_sign_in,
    client_for,
    set_cookies,
    sign_in,
    storage,
)
from test_typescript_room_feed import apply, feed
from test_typescript_room_ops import member

from conftest import TypeScriptTestServer
from room_cookies import plain_token_cookie_name

pytestmark = pytest.mark.own_server
COOKIE = "listapp-device"


@pytest.fixture(autouse=True)
def typescript_only(pytestconfig: pytest.Config) -> None:
    if pytestconfig.getoption("--browser-backend") != "typescript":
        pytest.skip("Build and select the TypeScript backend")


def private_path(server: TypeScriptTestServer) -> str:
    return f"/api/v1/rooms/{server.room_slug}/reminders"


def write(**fields: Any) -> dict[str, Any]:
    return {"op_id": str(uuid4()), **fields}


def ok(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def enroll(client: httpx.Client, path: str, **fields: Any) -> dict[str, Any]:
    response = client.post(f"{path}/enrollment", json=write(**fields))
    return ok(response)["enrollment"]


def private_rows(server: TypeScriptTestServer) -> tuple[list[tuple], ...]:
    return (
        server.query("SELECT * FROM reminder_installations ORDER BY id"),
        server.query(
            "SELECT * FROM reminder_enrollments ORDER BY installation_id, room_id"
        ),
        server.query("SELECT * FROM reminder_policies ORDER BY id"),
        server.query(
            "SELECT * FROM reminder_policy_rules ORDER BY policy_id, position"
        ),
        server.query("SELECT * FROM reminder_processed_ops ORDER BY id"),
    )


def test_private_cookie_and_explicit_resume(server: TypeScriptTestServer) -> None:
    # PrivateAccess, ExplicitEnrollment, DeviceSettings and RevisionsAndReplay.
    path = private_path(server)
    session = f"/api/v1/rooms/{server.room_slug}/session"
    with member(server) as client, client_for(server.url) as stranger:
        assert_error(stranger.get(f"{path}/preferences"), 401, "not_authenticated")
        assert ok(client.get(f"{path}/preferences/device")) == {"device": None}
        assert ok(client.get(f"{path}/preferences")) == {
            "enrollment": {"state": "not_enrolled", "revision": None}
        }
        assert not client.cookies.get(COOKIE)
        assert_error(client.get(f"{path}/policy"), 403, "not_enrolled")
        assert_error(
            client.patch(
                f"{path}/preferences/device", json=write(base_revision=1, paused=True)
            ),
            403,
            "not_enrolled",
        )
        body = write(timezone="Europe/Oslo", mode="scheduled")
        first = client.post(f"{path}/enrollment", json=body)
        first_view = ok(first)["enrollment"]
        assert first_view["state"] == "active"
        assert first_view["revision"] == 1
        [cookie] = set_cookies(first).values()
        assert cookie.key == COOKIE
        assert cookie["httponly"] and cookie["samesite"].lower() == "lax"
        assert cookie["path"] == "/" and cookie["max-age"] == "31536000"
        assert not cookie["secure"] and not cookie["domain"]
        assert len(cookie.value) == 43 and cookie.value not in first.text
        assert server.query("SELECT secret_hash FROM reminder_installations") == [
            (hashlib.sha256(cookie.value.encode()).hexdigest(),)
        ]
        before = private_rows(server)
        replay = client.post(f"{path}/enrollment", json=body)
        assert ok(replay) == first.json() and not set_cookies(replay)
        assert private_rows(server) == before
        assert_error(
            client.patch(
                f"{path}/preferences", json={"op_id": body["op_id"], "base_revision": 1}
            ),
            409,
            "op_id_reused",
        )

        # The installation namespace is separate from its room enrollment.
        device_patch = {"op_id": body["op_id"], "base_revision": 1, "quiet_hours": None}
        changed = ok(client.patch(f"{path}/preferences/device", json=device_patch))[
            "device"
        ]
        assert changed["quiet_hours"] is None and changed["revision"] == 2
        assert_error(
            client.patch(
                f"{path}/preferences/device", json=write(base_revision=1, paused=True)
            ),
            409,
            "revision_conflict",
        )
        assert_error(
            client.patch(
                f"{path}/preferences/device",
                json=write(base_revision=2, timezone="Unknown/Zone"),
            ),
            422,
            "invalid_request",
        )
        assert ok(client.get(f"{path}/preferences/device"))["device"] == changed
        assert client.delete(session).status_code == 204
        assert_error(
            client.post(f"{path}/enrollment", json=body), 401, "not_authenticated"
        )
        assert sign_in(client, server.room_slug, server.password).status_code == 200
        before = private_rows(server)
        replay = client.post(f"{path}/enrollment", json=body)
        assert ok(replay)["enrollment"] == first_view | {"state": "needs_resume"}
        assert not set_cookies(replay) and private_rows(server) == before
        revoked = ok(client.get(f"{path}/preferences"))["enrollment"]
        assert revoked["revision"] == 2
        opt_out = ok(
            client.patch(
                f"{path}/preferences", json=write(base_revision=2, opted_out=True)
            )
        )["enrollment"]
        assert opt_out["state"] == "opted_out"
        assert ok(client.get(f"{path}/policy"))["effective"]["preset"] == "scheduled"
        resumed = enroll(client, path, base_revision=opt_out["revision"])
        assert resumed["state"] == "active" and resumed["revision"] == 4
        assert ok(client.get(f"{path}/preferences/device"))["device"] == changed

        with storage(server) as db:
            db.execute(
                "UPDATE reminder_enrollments SET expires_at = '2001-01-01T00:00:00Z'"
            )
        before = private_rows(server)
        assert (
            ok(client.get(f"{path}/preferences"))["enrollment"]["state"]
            == "needs_resume"
        )
        assert private_rows(server) == before
        with storage(server) as db:
            db.execute(
                "UPDATE reminder_installations SET expires_at = '2001-01-01T00:00:00Z'"
            )
        assert ok(client.get(f"{path}/preferences/device")) == {"device": None}
        assert_error(
            client.patch(f"{path}/preferences/device", json=device_patch),
            403,
            "not_enrolled",
        )
        fresh = client.post(f"{path}/enrollment", json=body)
        assert ok(fresh)["enrollment"]["revision"] == 1
        assert set_cookies(fresh)[COOKIE].value != cookie.value


def test_https_cookie_ignores_plain_device_secret(tmp_path: Path) -> None:
    server = TypeScriptTestServer(tmp_path)
    origin = "https://list.test"
    server.env["LISTR_TS_ORIGIN"] = origin
    try:
        server.start()
        slug = server.room_slug
        path = private_path(server)
        with client_for(server.url, origin) as client:
            token = assert_sign_in(
                sign_in(client, slug, server.password), slug, secure=True
            )
            room_cookie = f"__Host-{plain_token_cookie_name(slug)}={token}"
            body = write(timezone="UTC")
            response = client.post(
                f"{path}/enrollment", json=body, headers={"Cookie": room_cookie}
            )
            ok(response)
            [cookie] = set_cookies(response).values()
            assert cookie.key == "__Host-listapp-device"
            assert cookie["secure"] and cookie["httponly"] and cookie["path"] == "/"
            assert not cookie["domain"] and cookie["max-age"] == "31536000"
            assert cookie.value not in response.text
            for name in (COOKIE, cookie.key):
                found = ok(
                    client.get(
                        f"{path}/preferences/device",
                        headers={"Cookie": f"{room_cookie}; {name}={cookie.value}"},
                    )
                )["device"]
                assert (found is not None) is (name == cookie.key)
    finally:
        server.stop()


def test_existing_private_rows_replay_only_within_scope(
    server: TypeScriptTestServer,
) -> None:
    # Synthetic rows in the existing SQLite layout; no second server or oracle.
    path = private_path(server)
    room = path.removesuffix("/reminders")
    first_secret = "synthetic-existing-device"
    with member(server) as client, member(server) as other:
        # Reusing the ID of a shared change is safe in the private namespace.
        shared_id = str(uuid4())
        first_list = apply(client, room, "list.create", name="First", op_id=shared_id)[
            "result"
        ]["list_uid"]
        second_list = apply(client, room, "list.create", name="Second")["result"][
            "list_uid"
        ]
        old = "2001-01-01T00:00:00Z"
        future = "2099-01-01T00:00:00Z"
        body = {"op_id": shared_id, "base_revision": 0, "state": "off"}
        saved_policy = {
            "scope": "list",
            "state": "off",
            "preset": None,
            "summary_enabled": False,
            "rules": [],
            "revision": 1,
            "activated_at": "2001-01-01T00:00:00.000Z",
        }
        saved_response = {"policy": saved_policy, "effective": saved_policy}
        with storage(server) as db:
            [(room_id,)] = db.execute("SELECT id FROM rooms")
            [(token_hash, version)] = db.execute(
                "SELECT token_hash, authorization_version FROM room_access_tokens ORDER BY id LIMIT 1"
            )
            [(device_id,)] = db.execute(
                "INSERT INTO reminder_installations (secret_hash, timezone, created_at, expires_at, anchor_activated_at, timezone_activated_at) "
                "VALUES (?, 'America/New_York', ?, ?, ?, ?) RETURNING id",
                (
                    hashlib.sha256(first_secret.encode()).hexdigest(),
                    old,
                    future,
                    old,
                    old,
                ),
            )
            db.execute(
                "INSERT INTO reminder_enrollments (installation_id, room_id, token_hash, authorization_version, status, "
                "activated_at, expires_at, created_at, policy_activated_at, summary_activated_at) "
                "VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)",
                (device_id, room_id, token_hash, version, old, future, old, old, old),
            )
            [(list_id,)] = db.execute(
                "SELECT id FROM lists WHERE uid = ?", (first_list,)
            )
            db.execute(
                "INSERT INTO reminder_policies (installation_id, room_id, scope, list_id, state, summary_enabled, revision, activated_at) "
                "VALUES (?, ?, 'list', ?, 'off', 0, 1, ?)",
                (device_id, room_id, list_id, saved_policy["activated_at"]),
            )
            canonical = json.dumps(
                {
                    "action": "replace_policy",
                    **body,
                    "preset": None,
                    "rules": [],
                    "summary_enabled": False,
                    "summary_time": None,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            db.execute(
                "INSERT INTO reminder_processed_ops (scope, installation_id, room_id, op_id, request_hash, response_json, created_at) "
                "VALUES ('enrollment', ?, ?, ?, ?, ?, ?)",
                (
                    device_id,
                    room_id,
                    body["op_id"],
                    hashlib.sha256(f"list:{list_id}:{digest}".encode()).hexdigest(),
                    json.dumps(saved_response),
                    old,
                ),
            )
            db.execute(
                "INSERT INTO rooms (name, slug, password_hash) SELECT 'Other', 'other', password_hash FROM rooms WHERE id = ?",
                (room_id,),
            )
        target = f"{path}/lists/{first_list}/policy"
        client.cookies.set(COOKIE, first_secret)
        before = private_rows(server)
        assert (
            ok(client.get(f"{path}/preferences/device"))["device"]["timezone"]
            == "America/New_York"
        )
        assert ok(client.get(f"{path}/preferences"))["enrollment"]["state"] == "active"
        assert ok(client.put(target, json=body)) == saved_response
        assert (
            ok(client.put(f"{path}/lists/{list_id}/policy", json=body))
            == saved_response
        )
        assert_error(
            client.put(f"{path}/lists/{second_list}/policy", json=body),
            409,
            "op_id_reused",
        )
        assert_error(other.put(target, json=body), 403, "not_enrolled")
        other.cookies.set(COOKIE, "forged")
        assert_error(other.put(target, json=body), 403, "not_enrolled")
        assert sign_in(client, "other", server.password).status_code == 200
        other_path = "/api/v1/rooms/other/reminders"
        assert_error(
            client.put(f"{other_path}/lists/{first_list}/policy", json=body),
            403,
            "not_enrolled",
        )
        assert private_rows(server) == before
        enroll(client, other_path)
        before = private_rows(server)
        assert_error(
            client.put(f"{other_path}/lists/{first_list}/policy", json=body),
            404,
            "not_found",
        )
        assert private_rows(server) == before


def last_sunday(year: int, month: int) -> date:
    end = date(year, month, 31)
    return end - timedelta(days=(end.weekday() + 1) % 7)


def test_inheritance_dst_preview_and_no_shared_change(
    server: TypeScriptTestServer,
) -> None:
    # PrivatePolicy, ReadOnlyPreview, plus shared due fields and feed projection.
    path = private_path(server)
    room = path.removesuffix("/reminders")
    year = datetime.now(UTC).year + 1
    gap = last_sunday(year, 3)
    fold = last_sunday(year, 10)
    with member(server) as client:
        list_uid = apply(client, room, "list.create", name="Groceries")["result"][
            "list_uid"
        ]
        added = apply(client, room, "item.add", list_uid=list_uid, name="Milk")
        item_uid = added["result"]["item_uid"]
        apply(
            client,
            room,
            "item.edit",
            list_uid=list_uid,
            item_uid=item_uid,
            name="Milk",
            description="",
            base_seq=added["seq"],
            date=gap.isoformat(),
            due_time="02:30",
            due_timezone="Europe/Oslo",
        )
        shared_before = feed(client, room, 0)
        [shared_item] = shared_before["items"]
        assert shared_item["due_at"] == f"{gap}T01:00:00.000Z"
        assert not any(key.startswith("reminder_") for key in shared_item)
        enroll(client, path, timezone="Europe/Oslo", mode="scheduled")
        item = f"{path}/items/{item_uid}/policy"
        list_policy = f"{path}/lists/{list_uid}/policy"
        preview = f"{path}/preview"
        target = {"item_uid": item_uid}
        assert ok(client.get(item))["effective"]["scope"] == "room"
        assert [
            e["instant"] for e in ok(client.post(preview, json=target))["entries"]
        ] == [
            f"{gap - timedelta(days=1)}T01:30:00.000Z",
            f"{gap}T01:00:00.000Z",
        ]
        assert (
            ok(client.put(list_policy, json=write(base_revision=0, state="off")))[
                "policy"
            ]["revision"]
            == 1
        )
        assert ok(client.post(preview, json=target))["disabled_reasons"] == [
            "policy_off"
        ]
        fixed = {
            "kind": "fixed",
            "date": fold.isoformat(),
            "time": "02:30",
            "timezone": "Europe/Oslo",
        }
        custom = {"state": "replace", "preset": "custom", "rules": [fixed]}
        before = private_rows(server)
        draft = ok(client.post(preview, json=target | {"draft": custom}))
        [provisional] = draft["provisional_fixed_ids"]
        assert draft["entries"] == [
            {
                "kind": "rules",
                "keys": [f"fixed:{provisional}"],
                "instant": f"{fold}T00:30:00.000Z",
                "deferred_until": f"{fold}T07:00:00.000Z",
                "local_day": None,
            }
        ]
        assert private_rows(server) == before
        assert_error(
            client.post(
                preview,
                json=target
                | {"draft": custom | {"rules": [fixed | {"timezone": "Unknown/Zone"}]}},
            ),
            422,
            "invalid_request",
        )
        put = ok(client.put(item, json=write(base_revision=0, **custom)))
        [stored] = put["policy"]["rules"]
        assert stored["id"] != provisional
        assert ok(client.put(item, json=write(base_revision=1, **custom))) == put
        assert (
            ok(client.post(preview, json=target | {"draft": {"state": "inherit"}}))[
                "source"
            ]
            == "list"
        )
        reset = ok(client.put(item, json=write(base_revision=1, state="inherit")))
        assert reset["policy"]["activated_at"] and reset["policy"]["revision"] == 2
        assert (
            reset["effective"]["scope"] == "list"
            and reset["effective"]["state"] == "off"
        )
        assert (
            ok(client.put(list_policy, json=write(base_revision=1, state="inherit")))[
                "effective"
            ]["scope"]
            == "room"
        )
        room_policy = f"{path}/policy"
        summary = write(
            base_revision=0,
            state="replace",
            preset="daily_summary",
            summary_time="07:30",
        )
        assert ok(client.put(room_policy, json=summary))["policy"]["revision"] == 1
        assert (
            ok(client.get(f"{path}/preferences"))["enrollment"]["summary_time"]
            == "07:30"
        )
        forecast = ok(client.post(preview, json=target))
        assert len(forecast["entries"]) == 5
        assert forecast["entries"][0] == {
            "kind": "summary",
            "keys": [],
            "instant": f"{gap - timedelta(days=1)}T06:30:00.000Z",
            "deferred_until": f"{gap - timedelta(days=1)}T07:00:00.000Z",
            "local_day": (gap - timedelta(days=1)).isoformat(),
        }
        ok(
            client.patch(
                f"{path}/preferences/device", json=write(base_revision=1, paused=True)
            )
        )
        paused = ok(client.post(preview, json=target))
        assert paused["disabled_reasons"] == ["device_paused"] and not paused["entries"]
        assert feed(client, room, 0) == shared_before
