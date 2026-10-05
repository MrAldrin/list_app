"""Home-screen install manifests for the Svelte app under /app/.

Same rules as NiceGUI's (tests/test_room_installation.py): one app identity,
only the launch address changes, and no secrets in the manifest.
"""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from install_manifest import BASE_MANIFEST_PATH
from svelte_frontend import register_svelte_frontend

BASE_MANIFEST = json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    build = tmp_path / "build"
    build.mkdir()
    (build / "index.html").write_text("<!doctype html><html></html>")
    app = FastAPI()
    assert register_svelte_frontend(app, build)
    return TestClient(app)


def assert_manifest_headers(response) -> None:
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/manifest+json"
    assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_default_manifest_opens_the_start_page(client):
    response = client.get("/app/manifest.webmanifest")
    assert_manifest_headers(response)
    assert response.json() == {**BASE_MANIFEST, "start_url": "/app/"}


def test_room_manifest_opens_the_room_and_keeps_one_identity(client):
    response = client.get(
        "/app/room-manifest/home-ab12cd.webmanifest?admin=true&token=secret&password=secret"
    )
    assert_manifest_headers(response)
    manifest = response.json()
    assert manifest == {**BASE_MANIFEST, "start_url": "/app/room/home-ab12cd"}
    assert manifest["id"] == "/"
    assert manifest["scope"] == "/"
    assert "secret" not in response.text
    assert "admin" not in response.text


def test_room_manifest_does_not_tell_whether_a_room_exists(client):
    # No database lookup: any slug gets the same shape of answer, so the
    # manifest is never a way to find rooms. An unknown room's icon opens
    # its password prompt, which says "Wrong room or password."
    response = client.get("/app/room-manifest/no-such-room.webmanifest")
    assert_manifest_headers(response)
    assert response.json()["start_url"] == "/app/room/no-such-room"


def test_room_manifest_encodes_an_untrusted_slug(client):
    response = client.get("/app/room-manifest/room%22%3F%3E%3C%26%20%23.webmanifest")
    assert_manifest_headers(response)
    assert response.json()["start_url"] == "/app/room/room%22%3F%3E%3C%26%20%23"


def test_manifest_icons_are_served_by_the_main_app():
    import main

    app_client = TestClient(main.app)
    for icon in BASE_MANIFEST["icons"]:
        response = app_client.get(icon["src"])
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
    for path in (
        "/static/icons/apple-touch-icon.png",
        "/static/icons/favicon-32.png",
        "/static/icons/favicon-16.png",
    ):
        assert app_client.get(path).status_code == 200


def test_svelte_manifests_leave_nicegui_manifests_unchanged(client):
    import main

    app_client = TestClient(main.app)
    nicegui = app_client.get("/manifest.json").json()
    assert nicegui == BASE_MANIFEST
    assert nicegui["start_url"] == "/"
    client.get("/app/room-manifest/home.webmanifest")
    assert app_client.get("/manifest.json").json() == BASE_MANIFEST
