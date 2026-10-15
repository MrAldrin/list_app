"""Home-screen install manifests, icons and the old service worker's kill switch.

Phones that installed the app before the Svelte switch still use the old
`.json` addresses. The pages at the root link the `.webmanifest` addresses
(src/svelte_frontend.py). Both pairs answer with the same content, and only
`start_url` changes. See src/pwa_routes.py and docs/home-screen-installation.md.
"""

import json
import re

import pytest
from starlette.testclient import TestClient

from database_setup import db
from install_manifest import BASE_MANIFEST_PATH
from main import app
from pwa_routes import KILL_SWITCH_SCRIPT

BASE_MANIFEST = json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8"))
NO_STORE_MANIFEST = "no-cache, no-store, must-revalidate"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def assert_manifest_headers(response) -> None:
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/manifest+json"
    assert response.headers["cache-control"] == NO_STORE_MANIFEST
    assert response.headers["x-content-type-options"] == "nosniff"


def test_service_worker_route_is_the_kill_switch(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.text == KILL_SWITCH_SCRIPT


def test_kill_switch_unregisters_cleans_up_and_never_handles_requests():
    script = KILL_SWITCH_SCRIPT
    assert "self.skipWaiting()" in script
    assert "addEventListener('install'" in script
    assert "addEventListener('activate'" in script
    # Order in the activate handler: caches, unregister, reload open pages.
    positions = [
        script.index("caches.keys()"),
        script.index("caches.delete("),
        script.index("self.registration.unregister()"),
        script.index("client.navigate(client.url)"),
    ]
    assert positions == sorted(positions)
    assert "clients.matchAll({ type: 'window' })" in script
    # No fetch handler: the page and API requests go straight to the network.
    assert "'fetch'" not in script
    assert "respondWith" not in script
    assert not re.search(r"cache\.(put|add)", script)


def test_kill_switch_answers_head_and_is_not_an_api_page(client):
    assert client.head("/sw.js").status_code == 200
    # Never HTML: an old worker that gets a page back would stay installed.
    assert "<html" not in client.get("/sw.js").text.lower()


@pytest.mark.parametrize(
    "path", ["/manifest.json", "/static/manifest.json", "/manifest.webmanifest"]
)
def test_default_manifest_opens_the_start_page(client, path):
    response = client.get(path)
    assert_manifest_headers(response)
    assert response.json() == {**BASE_MANIFEST, "start_url": "/"}


@pytest.mark.parametrize("suffix", [".json", ".webmanifest"])
def test_room_manifest_opens_the_room_and_holds_no_secrets(client, suffix):
    response = client.get(
        f"/room-manifest/home-ab12cd{suffix}?admin=true&token=secret&password=secret"
    )
    assert_manifest_headers(response)
    manifest = response.json()
    assert manifest == {**BASE_MANIFEST, "start_url": "/room/home-ab12cd"}
    assert manifest["id"] == "/"
    assert manifest["scope"] == "/"
    assert "secret" not in response.text
    assert "admin" not in response.text


@pytest.mark.parametrize("suffix", [".json", ".webmanifest"])
def test_room_manifest_does_not_tell_whether_a_room_exists(client, suffix):
    slug = db.execute("SELECT slug FROM rooms").fetchone()[0]
    real = client.get(f"/room-manifest/{slug}{suffix}")
    unknown = client.get(f"/room-manifest/no-such-room{suffix}")
    assert_manifest_headers(real)
    assert_manifest_headers(unknown)
    assert real.json() == {**BASE_MANIFEST, "start_url": f"/room/{slug}"}
    # An unknown room's icon opens its password prompt, so the answer is the same shape.
    assert unknown.json() == {**BASE_MANIFEST, "start_url": "/room/no-such-room"}


def test_room_manifest_encodes_an_untrusted_slug(client):
    response = client.get("/room-manifest/room%22%3F%3E%3C%26%20%23.webmanifest")
    assert_manifest_headers(response)
    assert response.json()["start_url"] == "/room/room%22%3F%3E%3C%26%20%23"


def test_old_and_new_manifests_match(client):
    assert (
        client.get("/manifest.json").json()
        == client.get("/manifest.webmanifest").json()
    )
    assert (
        client.get("/room-manifest/x.json").json()
        == client.get("/room-manifest/x.webmanifest").json()
    )


def test_apple_touch_icon_fallback_routes(client):
    original = client.get("/static/icons/apple-touch-icon.png")
    assert original.status_code == 200
    assert original.content.startswith(b"\x89PNG\r\n\x1a\n")
    for path in ["/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == original.content


def test_favicon_is_the_png(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == client.get("/static/icons/favicon-32.png").content


def test_manifest_icons_are_served(client):
    for icon in BASE_MANIFEST["icons"]:
        response = client.get(icon["src"])
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
    for path in (
        "/static/icons/apple-touch-icon.png",
        "/static/icons/favicon-32.png",
        "/static/icons/favicon-16.png",
    ):
        assert client.get(path).status_code == 200


def test_the_old_service_worker_file_is_not_a_static_file(client):
    # Only the /sw.js route answers; the old file is gone from /static.
    response = client.get("/static/sw.js")
    assert response.status_code == 404


def test_the_old_cookie_endpoint_is_gone(client):
    response = client.post(
        "/_room-access/home",
        json={"token": "t"},
        headers={"Origin": "https://testserver", "X-Listapp-Request": "1"},
    )
    assert response.status_code in (404, 405)
    assert "set-cookie" not in response.headers
