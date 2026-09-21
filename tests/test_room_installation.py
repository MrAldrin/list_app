"""Installation metadata must select a room without granting access to it."""

import asyncio
import json
from unittest.mock import AsyncMock
from urllib.parse import quote

import pytest
from nicegui import Client, ui
from nicegui.page import page
from starlette.testclient import TestClient

import main
from database_setup import db
from room_access import RoomAccessStatus


def test_room_manifest_is_isolated_and_credential_free():
    slug = db.execute("SELECT slug FROM rooms").fetchone()[0]
    client = TestClient(main.app)
    baseline = client.get("/manifest.json").json()
    response = client.get(
        f"/room-manifest/{slug}.json?admin=true&token=secret&password=secret"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/manifest+json"
    assert "no-store" in response.headers["cache-control"]
    expected = {**baseline, "start_url": f"/room/{slug}"}
    assert response.json() == expected
    assert expected["id"] == "/"
    assert expected["scope"] == "/"
    assert "secret" not in response.text
    assert client.get("/manifest.json").json() == baseline
    assert client.get("/static/manifest.json").json() == baseline

    db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
        ("Other private name", "other-room", "unused"),
    )
    db.commit()
    other = client.get("/room-manifest/other-room.json").json()
    assert other == {**baseline, "start_url": "/room/other-room"}
    assert "Other private name" not in json.dumps(other)
    assert client.get(f"/room-manifest/{slug}.json").json() == expected


def test_missing_and_deleted_rooms_have_no_install_manifest():
    client = TestClient(main.app)
    slug = db.execute("SELECT slug FROM rooms").fetchone()[0]
    assert client.get("/room-manifest/missing.json").status_code == 404
    db.execute("DELETE FROM lists")
    db.execute("DELETE FROM rooms")
    db.commit()
    assert client.get(f"/room-manifest/{slug}.json").status_code == 404


@pytest.mark.parametrize("admin", [None, "true"])
def test_fresh_room_launch_still_requires_password(monkeypatch, admin):
    slug = db.execute("SELECT slug FROM rooms").fetchone()[0]
    # Fresh installation has no browser token. Keep the actual room page and
    # password UI; isolate only the browser/session access lookup.
    lookup = AsyncMock(return_value=(None, RoomAccessStatus.INVALID))
    monkeypatch.setattr(main, "_room_access_from_browser", lookup)

    async def render():
        with Client(page("/room/{slug}")) as client:
            await main.room_page(slug, admin=admin)
            assert client.head_html.count('rel="manifest"') == 1
            assert f'href="/room-manifest/{slug}.json"' in client.head_html
            assert "admin=true" not in client.head_html
            assert any(
                isinstance(element, ui.input)
                and element.props.get("type") == "password"
                for element in client.elements.values()
            )
            assert not any(
                isinstance(element, ui.label) and element.text == "Room not found"
                for element in client.elements.values()
            )

    asyncio.run(render())
    lookup.assert_awaited_once()


def test_manifest_links_are_per_client_and_escape_untrusted_slug():
    slug = 'room"?><& #'
    with Client(page("/room/{slug}")) as first:
        main._add_install_manifest(slug)
    with Client(page("/")) as second:
        main._add_install_manifest()
    assert first.head_html.count('rel="manifest"') == 1
    assert f"/room-manifest/{quote(slug, safe='')}.json" in first.head_html
    assert second.head_html.count('rel="manifest"') == 1
    assert 'href="/manifest.json"' in second.head_html
    assert "room-manifest" not in second.head_html


def test_deleted_room_launch_keeps_recovery_metadata():
    async def render():
        with Client(page("/room/{slug}")) as client:
            await main.room_page("missing")
            assert 'href="/manifest.json"' in client.head_html
            assert any(
                isinstance(element, ui.label) and element.text == "Room not found"
                for element in client.elements.values()
            )

    asyncio.run(render())
