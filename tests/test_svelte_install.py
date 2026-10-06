"""Home-screen install manifests of the pages at the root.

One app identity, only the launch address changes, and no secrets in the
manifest. The old `.json` addresses are tested in tests/test_pwa_routes.py.
"""

import json

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from install_manifest import BASE_MANIFEST_PATH
from pwa_routes import register_pwa_routes

BASE_MANIFEST = json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_pwa_routes(app)
    return TestClient(app)


def assert_manifest_headers(response) -> None:
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/manifest+json"
    assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_default_manifest_opens_the_start_page(client):
    response = client.get("/manifest.webmanifest")
    assert_manifest_headers(response)
    assert response.json() == {**BASE_MANIFEST, "start_url": "/"}


def test_room_manifest_opens_the_room_and_keeps_one_identity(client):
    response = client.get(
        "/room-manifest/home-ab12cd.webmanifest?admin=true&token=secret&password=secret"
    )
    assert_manifest_headers(response)
    manifest = response.json()
    assert manifest == {**BASE_MANIFEST, "start_url": "/room/home-ab12cd"}
    assert manifest["id"] == "/"
    assert manifest["scope"] == "/"
    assert "secret" not in response.text
    assert "admin" not in response.text


def test_room_manifest_does_not_tell_whether_a_room_exists(client):
    # No database lookup: any slug gets the same shape of answer, so the
    # manifest is never a way to find rooms. An unknown room's icon opens
    # its password prompt, which says "Wrong room or password."
    response = client.get("/room-manifest/no-such-room.webmanifest")
    assert_manifest_headers(response)
    assert response.json()["start_url"] == "/room/no-such-room"


def test_room_manifest_encodes_an_untrusted_slug(client):
    response = client.get("/room-manifest/room%22%3F%3E%3C%26%20%23.webmanifest")
    assert_manifest_headers(response)
    assert response.json()["start_url"] == "/room/room%22%3F%3E%3C%26%20%23"
