import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from starlette.testclient import TestClient

from main import app


def test_service_worker_route():
    client = TestClient(app)
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"
    assert "self.skipWaiting()" in response.text


def test_manifest_routes():
    client = TestClient(app)
    for path in ["/manifest.json", "/static/manifest.json"]:
        response = client.get(path)
        assert response.status_code == 200
        assert (
            response.headers["cache-control"] == "no-cache, no-store, must-revalidate"
        )


def test_apple_touch_icon_fallback_routes() -> None:
    client = TestClient(app)
    original = client.get("/static/icons/apple-touch-icon.png")
    assert original.status_code == 200
    assert original.content.startswith(b"\x89PNG\r\n\x1a\n")
    for path in ["/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == original.content


def test_favicon_is_a_file_nicegui_can_serve():
    from nicegui import helpers

    from main import FAVICON_PATH

    # NiceGUI serves /favicon.ico with FileResponse only for real files;
    # a URL such as "/static/..." makes every favicon request fail.
    assert helpers.is_file(FAVICON_PATH)
