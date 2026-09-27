"""Opt-in HTTPS offline launch with trust confined to disposable browser profiles."""

import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest
from conftest import TestServer
from playwright.sync_api import Browser, expect
from test_offline_readonly import prepare_snapshot_data


def run(*args: str) -> None:
    subprocess.run(args, check=True, capture_output=True, timeout=20)


def local_ca(directory: Path) -> tuple[Path, Path, Path]:
    ca_key, ca_cert = directory / "ca.key", directory / "ca.pem"
    key, cert, request = (
        directory / "server.key",
        directory / "server.pem",
        directory / "server.csr",
    )
    extensions = directory / "server.ext"
    extensions.write_text(
        "subjectAltName=IP:127.0.0.1\n"
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\n"
    )
    run(
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-days",
        "1",
        "-subj",
        "/CN=ListR disposable test CA",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        "-keyout",
        str(ca_key),
        "-out",
        str(ca_cert),
    )
    run(
        "openssl",
        "req",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-subj",
        "/CN=127.0.0.1",
        "-keyout",
        str(key),
        "-out",
        str(request),
    )
    run(
        "openssl",
        "x509",
        "-req",
        "-in",
        str(request),
        "-CA",
        str(ca_cert),
        "-CAkey",
        str(ca_key),
        "-CAcreateserial",
        "-days",
        "1",
        "-out",
        str(cert),
        "-extfile",
        str(extensions),
    )
    return ca_cert, cert, key


def trust_in_test_profile(certutil: str, directory: Path, ca_cert: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    run(certutil, "-N", "-d", f"sql:{directory}", "--empty-password")
    run(
        certutil,
        "-A",
        "-d",
        f"sql:{directory}",
        "-n",
        "ListR disposable CA",
        "-t",
        "C,,",
        "-i",
        str(ca_cert),
    )


@pytest.mark.parametrize("browser", ["chromium", "firefox"], indirect=True)
def test_trusted_https_cookie_and_cold_offline_navigation(
    tmp_path: Path, browser: Browser
) -> None:
    certutil = os.environ.get("LISTR_TEST_CERTUTIL") or shutil.which("certutil")
    if not certutil:
        pytest.fail(
            "Install NSS certutil locally or set LISTR_TEST_CERTUTIL; never import into system trust"
        )
    ca_cert, cert, key = local_ca(tmp_path)
    # The server readiness probe trusts only the disposable CA.
    server = TestServer(tmp_path, tls_cert=cert, tls_key=key, tls_ca=ca_cert)
    try:
        server.start()
        room_slug, _, _ = prepare_snapshot_data(server)
        url = f"{server.url}/room/{room_slug}"
        profile = tmp_path / "profile"
        if browser.browser_type.name == "chromium":
            # Chrome on Linux uses an NSS database under HOME. Supply a temp HOME
            # only to this browser process, never the user's ~/.pki/nssdb.
            home = tmp_path / "browser-home"
            trust_in_test_profile(certutil, home / ".pki" / "nssdb", ca_cert)
            launch_args = {"env": {**os.environ, "HOME": str(home)}}
        else:
            trust_in_test_profile(certutil, profile, ca_cert)
            launch_args = {}
        context = browser.browser_type.launch_persistent_context(
            str(profile), headless=True, ignore_https_errors=False, **launch_args
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url)
            page.get_by_label("Room Password", exact=True).fill(server.password)
            page.get_by_role("button", name="Enter", exact=True).click()
            expect(page.get_by_role("button", name="Add New List")).to_be_visible()
            page.wait_for_function(
                """async (slug) => {
                        const record = await window.ListROfflineStorage?.readRecord();
                        return navigator.serviceWorker.controller &&
                            record?.snapshot.room.slug === slug &&
                            record.snapshot.lists.some(l => l.name === 'Daily');
                    }""",
                arg=room_slug,
                timeout=20_000,
            )
            assert (
                page.evaluate(
                    "(slug) => localStorage.getItem('listapp_room_token_' + slug)",
                    room_slug,
                )
                is None
            )
            cookies = context.cookies()
            assert any(
                c["name"].startswith("__Host-listapp-room-")
                and c["secure"]
                and c["httpOnly"]
                for c in cookies
            )
            paths = page.evaluate(
                """async () => {
                        const paths = [];
                        for (const name of await caches.keys()) {
                            for (const request of await (await caches.open(name)).keys()) {
                                paths.push(new URL(request.url).pathname);
                            }
                        }
                        return paths.sort();
                    }"""
            )
            assert paths == [
                "/static/offline-shell.css",
                "/static/offline-shell.html",
                "/static/offline-shell.js",
                "/static/offline-storage.js",
            ]
            cached_content = page.evaluate(
                """async () => {
                    const entries = [];
                    for (const name of await caches.keys()) {
                        const cache = await caches.open(name);
                        for (const request of await cache.keys()) {
                            entries.push(request.url + (await (await cache.match(request)).text()));
                        }
                    }
                    return entries.join('\\n');
                }"""
            )
            assert room_slug not in cached_content
            assert server.password not in cached_content
            assert "Checked apples" not in cached_content
            saved_at = page.evaluate(
                "window.ListROfflineStorage.readRecord().then(r => r.saved_at)"
            )
            context.set_offline(True)
            server.stop()
            page.goto(url, timeout=15_000)
            expect(page.get_by_text("Offline · read only", exact=True)).to_be_visible()
            expect(page.get_by_text("Checked apples", exact=True)).to_be_visible()
            assert (
                page.evaluate(
                    "window.ListROfflineStorage.readRecord().then(r => r.saved_at)"
                )
                == saved_at
            )
            assert page.locator("input, button").count() == 0
            page.goto(server.url, timeout=15_000)  # Older root-launch icons.
            expect(page.get_by_text("Checked apples", exact=True)).to_be_visible()
            context.set_offline(False)
            server.start()
            page.goto(url)
            expect(page.get_by_role("button", name="Add New List")).to_be_visible()

            # A reachable temporary error must not pretend the saved HTTPS
            # copy was refreshed or clear it. The next definitive denial must.
            server.stop()
            context.set_offline(True)
            page.goto(url, timeout=15_000)
            expect(page.get_by_text("Checked apples", exact=True)).to_be_visible()
            old_record = page.evaluate("window.ListROfflineStorage.readRecord()")
            old_saved_at = old_record["saved_at"]
            server.start()
            endpoint = f"**/api/offline/rooms/{room_slug}/snapshot"
            context.route(
                endpoint, lambda route: route.fulfill(status=503, body="unavailable")
            )
            try:
                context.set_offline(False)
                with page.expect_response(
                    lambda response: (
                        response.url.endswith(
                            f"/api/offline/rooms/{room_slug}/snapshot"
                        )
                        and response.status == 503
                    )
                ):
                    page.evaluate("window.dispatchEvent(new Event('online'))")
                expect(
                    page.get_by_text(
                        "Could not verify the latest copy · read only", exact=True
                    )
                ).to_be_visible()
                expect(page.get_by_text("Checked apples", exact=True)).to_be_visible()
                assert (
                    page.evaluate(
                        "window.ListROfflineStorage.readRecord().then(r => r.saved_at)"
                    )
                    == old_saved_at
                )
            finally:
                context.unroute(endpoint)

            # A successful cookie-backed fetch followed by an IndexedDB write
            # failure must also keep the prior complete copy and timestamp.
            list_id = server.query("SELECT id FROM lists WHERE slug = 'daily-list'")[0][
                0
            ]
            with sqlite3.connect(server.database) as connection:
                connection.execute(
                    """INSERT INTO items (name, done, list_id, active_tags, description, quantity)
                       VALUES (?, 0, ?, '[]', '', 1)""",
                    ("New HTTPS item", list_id),
                )
            page.evaluate(
                """() => {
                    window.__offlinePut = IDBObjectStore.prototype.put;
                    IDBObjectStore.prototype.put = function () {
                        throw new DOMException('test quota failure', 'QuotaExceededError');
                    };
                }"""
            )
            try:
                with page.expect_response(
                    lambda response: (
                        response.url.endswith(
                            f"/api/offline/rooms/{room_slug}/snapshot"
                        )
                        and response.status == 200
                    )
                ):
                    page.evaluate("window.dispatchEvent(new Event('online'))")
                expect(
                    page.get_by_text(
                        "Could not save the latest copy · read only", exact=True
                    )
                ).to_be_visible()
                assert (
                    page.evaluate("window.ListROfflineStorage.readRecord()")
                    == old_record
                )
                expect(page.get_by_text("New HTTPS item", exact=True)).to_have_count(0)
            finally:
                page.evaluate(
                    "() => { IDBObjectStore.prototype.put = window.__offlinePut; }"
                )
            page.evaluate("window.dispatchEvent(new Event('online'))")
            expect(page.get_by_text("New HTTPS item", exact=True)).to_be_visible()
            page.wait_for_function(
                """async (previous) => {
                    const record = await window.ListROfflineStorage.readRecord();
                    return record?.saved_at !== previous &&
                        record.snapshot.lists.some(list =>
                            list.items.some(item => item.name === 'New HTTPS item'));
                }""",
                arg=old_saved_at,
            )
            # A still-disconnected browser may read its old copy after a
            # password reset. A reachable definitive denial must clear it.
            server.stop()
            context.set_offline(True)
            page.reload(timeout=15_000)
            expect(page.get_by_text("Checked apples", exact=True)).to_be_visible()
            with sqlite3.connect(server.database) as connection:
                connection.execute(
                    "UPDATE rooms SET authorization_version = authorization_version + 1 WHERE slug = ?",
                    (room_slug,),
                )
            page.reload(timeout=15_000)
            expect(page.get_by_text("Checked apples", exact=True)).to_be_visible()
            server.start()
            context.set_offline(False)
            page.evaluate("window.dispatchEvent(new Event('online'))")
            page.wait_for_function(
                "async () => (await window.ListROfflineStorage.readRecord()) === null",
                timeout=15_000,
            )
            expect(page.get_by_text("Checked apples", exact=True)).to_have_count(0)
            expect(
                page.get_by_text("Room access could not be confirmed.", exact=False)
            ).to_be_visible()
        finally:
            context.close()
    finally:
        server.stop()
        log = server.log_path.read_text() if server.log_path.exists() else ""
        assert "Traceback (most recent call last)" not in log, log
