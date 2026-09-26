from starlette.testclient import TestClient

import main


def test_generic_offline_shell_assets_are_served_without_room_data():
    client = TestClient(main.app)
    assets = (
        "/static/offline-shell.html",
        "/static/offline-shell.css",
        "/static/offline-storage.js",
        "/static/offline-shell.js",
        "/static/offline-client.js",
    )
    for path in assets:
        response = client.get(path)
        assert response.status_code == 200
        assert response.content

    html = client.get(assets[0]).text
    assert "offline-storage.js" in html
    assert "offline-shell.js" in html
    assert "checking room access" in html.lower()
    assert "<input" not in html.lower()
    assert "<button" not in html.lower()
    assert "room password" not in html.lower()
    assert "token" not in html.lower()
