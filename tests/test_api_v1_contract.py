"""Decode representative Python API responses with the shared Effect schemas."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from api_helpers import APP_PASSWORD, client_for, default_list, home, new_id
from httpx2 import Response
from test_api_events import SseConnection, run, token_for

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def test_python_responses_decode_with_effect_schema() -> None:
    bun = shutil.which("bun")
    if bun is None or not (FRONTEND / "node_modules/effect/package.json").is_file():
        pytest.skip("Requires Bun and `bun install --frozen-lockfile` in frontend/")

    _, slug = home()
    _, list_uid = default_list()
    room_url = f"/api/v1/rooms/{slug}"
    browser = client_for()
    samples: list[dict[str, Any]] = []

    def record(
        route: str, response: Response, *, error_status: int | None = None
    ) -> dict[str, Any]:
        if error_status is None:
            response.raise_for_status()
        else:
            assert response.status_code == error_status
        if response.status_code == 204:
            assert response.content == b""
            body = None
        else:
            body = response.json()
        samples.append({"route": route, "status": response.status_code, "body": body})
        return body or {}

    session = "GET /rooms/{slug}/session"
    unauthenticated = browser.get(f"{room_url}/session")
    assert (
        record(session, unauthenticated, error_status=401)["error"]["code"]
        == "not_authenticated"
    )
    record(
        "POST /rooms/{slug}/session",
        browser.post(f"{room_url}/session", json={"password": "pw"}),
    )
    record(session, browser.get(f"{room_url}/session"))

    def write(body: dict[str, Any]) -> dict[str, Any]:
        return record(
            "POST /rooms/{slug}/ops", browser.post(f"{room_url}/ops", json=body)
        )

    add = {"op_id": new_id(), "type": "item.add", "list_uid": list_uid, "name": "Tea"}
    added = write(add)
    assert added["status"] == "applied"
    assert write(add) == added
    item_uid = added["result"]["item_uid"]
    edit = {
        "type": "item.edit",
        "list_uid": list_uid,
        "item_uid": item_uid,
        "base_seq": added["result"]["changed_seq"],
        "name": "tea",
        "description": "",
        "date": "2099-04-02",
        "due_time": "09:00",
    }
    assert write({**edit, "op_id": new_id()})["code"] == "invalid_due"
    assert (
        write({**edit, "op_id": new_id(), "due_timezone": "Nope/Zone"})["code"]
        == "time_zone_unavailable"
    )
    assert (
        write({**edit, "op_id": new_id(), "due_timezone": "UTC"})["status"] == "applied"
    )
    record("GET /rooms/{slug}/changes", browser.get(f"{room_url}/changes?since=0"))
    share = record(
        "POST /rooms/{slug}/lists/{list_uid}/share-link",
        browser.post(f"{room_url}/lists/{list_uid}/share-link", json={}),
    )
    record(
        "GET /share/{token}/changes",
        client_for().get(f"/api/v1/share/{share['token']}/changes?since=0"),
    )

    prefs = f"{room_url}/reminders/preferences"
    record("GET /rooms/{slug}/reminders/preferences", browser.get(prefs))
    record(
        "GET /rooms/{slug}/reminders/preferences/device", browser.get(f"{prefs}/device")
    )
    record(
        "POST /rooms/{slug}/reminders/enrollment",
        browser.post(
            f"{room_url}/reminders/enrollment",
            json={"op_id": new_id(), "timezone": "UTC"},
        ),
    )
    record(
        "GET /rooms/{slug}/reminders/preferences/device", browser.get(f"{prefs}/device")
    )
    record(
        "GET /rooms/{slug}/reminders/policy",
        browser.get(f"{room_url}/reminders/policy"),
    )
    record(
        "POST /rooms/{slug}/reminders/preview",
        browser.post(f"{room_url}/reminders/preview", json={"item_uid": item_uid}),
    )
    admin = client_for()
    record(
        "POST /admin/session",
        admin.post("/api/v1/admin/session", json={"password": APP_PASSWORD}),
    )
    record("POST /admin/invitations", admin.post("/api/v1/admin/invitations", json={}))
    record("DELETE /rooms/{slug}/session", browser.delete(f"{room_url}/session"))

    async def read_event() -> None:
        stream = SseConnection(slug, token_for(slug))
        await stream.open()
        try:
            assert stream.status == 200
            name, data = await stream.next_event()
            samples.append(
                {
                    "route": "GET /rooms/{slug}/events",
                    "status": stream.status,
                    "body": {"event": name, "data": json.loads(data)},
                }
            )
        finally:
            await stream.close()

    run(read_event)
    decoded = subprocess.run(
        [bun, "scripts/decode-api-v1-responses.ts"],
        cwd=FRONTEND,
        input=json.dumps(samples),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert decoded.returncode == 0, decoded.stderr
