"""Disposable HTTPS smoke for cookie-only offline snapshots."""

import hashlib
import sqlite3
import subprocess

import pytest
from conftest import TestServer
from playwright.sync_api import expect


@pytest.fixture
def secure_server(tmp_path):
    cert = tmp_path / "local.crt"
    key = tmp_path / "local.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=127.0.0.1",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
        ],
        capture_output=True,
        check=True,
        timeout=15,
    )
    server = TestServer(tmp_path, tls_cert=cert, tls_key=key)
    try:
        server.start()
        yield server
    finally:
        server.stop()
        log = server.log_path.read_text() if server.log_path.exists() else ""
        assert "Traceback (most recent call last)" not in log, log


@pytest.mark.parametrize("browser", ["chromium", "firefox"], indirect=True)
def test_secure_cookie_snapshot_and_revocation(secure_server, browser):
    server = secure_server
    room_slug = server.query("SELECT slug FROM rooms WHERE name = 'Home'")[0][0]
    room_url = f"{server.url}/room/{room_slug}"
    cookie_name = (
        "__Host-listapp-room-" + hashlib.sha256(room_slug.encode()).hexdigest()
    )
    context = browser.new_context(ignore_https_errors=True)
    copied_context = None
    try:
        page = context.new_page()
        requests = []
        page.on(
            "request",
            lambda request: (
                requests.append(request) if "/api/offline/" in request.url else None
            ),
        )
        page.goto(room_url)
        page.get_by_label("Room Password", exact=True).fill(server.password)
        page.get_by_role("button", name="Enter", exact=True).click()
        expect(page.get_by_role("button", name="Add New List")).to_be_visible()
        page.wait_for_function(
            """async (slug) => {
                if (!window.ListROfflineStorage || !navigator.serviceWorker.controller) return false;
                const record = await window.ListROfflineStorage.readRecord();
                return record?.snapshot.room.slug === slug;
            }""",
            arg=room_slug,
            timeout=20_000,
        )
        cookie = next(c for c in context.cookies() if c["name"] == cookie_name)
        assert cookie["secure"] and cookie["httpOnly"]
        assert (
            page.evaluate(f"localStorage.getItem('listapp_room_token_{room_slug}')")
            is None
        )
        assert requests and all(
            "x-listapp-room-token" not in r.headers for r in requests
        )
        assert all("token=" not in r.url for r in requests)

        # An installed-like context with copied cookies but no localStorage can fetch.
        copied_context = browser.new_context(ignore_https_errors=True)
        copied_context.add_cookies([cookie])
        copied_page = copied_context.new_page()
        copied_page.goto(room_url)
        expect(copied_page.get_by_role("button", name="Add New List")).to_be_visible()
        copied_page.wait_for_function(
            """async (slug) => {
                const storage = window.ListROfflineStorage;
                return Boolean(storage && (await storage.readRecord())?.snapshot.room.slug === slug);
            }""",
            arg=room_slug,
            timeout=20_000,
        )

        # The self-signed test certificate exercises cookie-backed fetching, not
        # installed-app offline launch (browser trust and device behavior differ).
        with sqlite3.connect(server.database) as connection:
            connection.execute(
                "UPDATE rooms SET authorization_version = authorization_version + 1 WHERE slug = ?",
                (room_slug,),
            )
        page.goto(room_url)
        expect(page.get_by_label("Room Password", exact=True)).to_be_visible()
        page.wait_for_function(
            "async () => (await window.ListROfflineStorage.readRecord()) === null",
            timeout=15_000,
        )
    finally:
        if copied_context:
            copied_context.close()
        context.close()
