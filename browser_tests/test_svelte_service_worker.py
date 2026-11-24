"""The Svelte shell is complete before it can serve an offline navigation.

Also: a tab from a replaced build reloads onto the new build (stale lazy chunks).
"""

import hashlib
import json
import mimetypes
import re
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect
from svelte_app import wait_until

from api.version import API_VERSION, API_VERSION_HEADER
from conftest import ROOT, TS_ENTRY, TypeScriptTestServer

FRONTEND_BUILD = ROOT / "frontend" / "build"
WORKER_PREFIX = "listr-app-shell-"
WORKER_SCRIPT = "/service-worker.js"


def _cache_names(page):
    return page.evaluate("caches.keys()")


def _wait_for_controlled_page(page, url: str):
    page.goto(url)
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    # Persistent WebKit exits when its last tab closes. Keep the replacement
    # blank until the old tab closes; it must load the app without warming it.
    replacement = page.context.new_page()
    page.close()
    page = replacement
    page.goto(url)
    page.wait_for_function(
        "navigator.serviceWorker.controller?.scriptURL.endsWith('/service-worker.js')"
    )
    return page


class BuildServerState:
    build_path = FRONTEND_BUILD
    failed_asset: str | None = None
    unauthorized_room: str | None = None
    failed_asset_requests: list[str]

    def __init__(self):
        self.failed_asset_requests = []


class BuiltAppHandler(BaseHTTPRequestHandler):
    state: BuildServerState

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == WORKER_SCRIPT:
            body = (self.state.build_path / "service-worker.js").read_bytes()
            self._send(body, "text/javascript", "no-cache")
            return

        if self.state.failed_asset == path:
            self.state.failed_asset_requests.append(path)
            self._send(b"interrupted update", "text/plain", "no-store", 503)
            return

        if (
            self.state.unauthorized_room
            and path == f"/api/v1/rooms/{self.state.unauthorized_room}/session"
        ):
            self._send(
                b'{"error":{"code":"not_authenticated","message":"Sign in to this room."}}',
                "application/json",
                "no-store",
                401,
            )
            return

        if path == "/api/v1/last-room":
            self._send(b'{"slug":null}', "application/json", "no-store")
            return

        if path == "/api" or path.startswith("/api/") or path.startswith("/static/"):
            self._send(b"", "text/plain", "no-store", 404)
            return

        relative = path.lstrip("/")
        file = (self.state.build_path / relative).resolve()
        if not file.is_relative_to(self.state.build_path) or not file.is_file():
            file = self.state.build_path / "index.html"
        content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        cache = (
            "public, max-age=31536000, immutable"
            if path.startswith("/_app/immutable/")
            else "no-store"
            if path in ("", "/")
            else "no-cache"
        )
        self._send(file.read_bytes(), content_type, cache)

    def _send(
        self, body: bytes, content_type: str, cache_control: str, status=200
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if content_type == "application/json":
            self.send_header(API_VERSION_HEADER, str(API_VERSION))
        self.send_header("Cache-Control", cache_control)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


class BuiltAppServer:
    original_build = FRONTEND_BUILD

    def __init__(self):
        self.state = BuildServerState()
        self.port = 0
        self.httpd = None
        self.thread = None
        self.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        if self.httpd:
            return
        handler = type("TestBuiltAppHandler", (BuiltAppHandler,), {"state": self.state})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if not self.httpd:
            return
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        self.httpd = None
        self.thread = None

    def switch_build(self, build: Path, failed_asset: str | None = None) -> None:
        self.state.failed_asset = failed_asset
        self.state.build_path = build


class BunBuildServer(TypeScriptTestServer):
    """Switch real Bun deploys on the same origin with the same test database."""

    original_build = TS_ENTRY.parent

    def switch_build(self, build: Path, failed_asset: str | None = None) -> None:
        if failed_asset is not None:
            # Remove a precache asset from the deploy, but keep it in the worker's list.
            (build / "client" / failed_asset.lstrip("/")).unlink()
        _refresh_asset_table(build)
        self.stop()
        self.entry = build / "index.js"
        self.start()


def _refresh_asset_table(build: Path) -> None:
    """Update the adapter's file table to match an intentionally edited build."""
    asset_table = build / "adapter-bun.js"
    result = []
    for line in asset_table.read_text().splitlines():
        if line.startswith('["client_asset",'):
            kind, url, name, meta = json.loads(line.rstrip(","))
            file = build / "client" / name
            if file.exists():
                meta["hash"] = hashlib.blake2b(
                    file.read_bytes(), digest_size=32
                ).hexdigest()[:16]
                meta["mtime"] = file.stat().st_mtime_ns // 1_000_000
                line = json.dumps([kind, url, name, meta]) + ","
        result.append(line)
    asset_table.write_text("\n".join(result) + "\n")


@pytest.fixture
def built_app_server(svelte_assets, pytestconfig, tmp_path):
    if pytestconfig.getoption("--browser-backend") == "typescript":
        # Build copies resolve the pinned dependencies without writing to them.
        (tmp_path / "node_modules").symlink_to(
            ROOT / "frontend" / "node_modules", target_is_directory=True
        )
        server = BunBuildServer(tmp_path)
        server.start()
    else:
        server = BuiltAppServer()
    try:
        yield server
    finally:
        server.stop()


def _changed_build(
    server,
    tmp_path: Path,
    version: str,
    *,
    realistic: bool = False,
    new_version_file: bool = False,
    retain_old_entry: bool = False,
) -> tuple[Path, str]:
    """Make a disposable second deploy with a new worker and a real lazy chunk URL."""
    build = tmp_path / version
    shutil.copytree(server.original_build, build)
    bun_build = isinstance(server, BunBuildServer)
    client = build / "client" if bun_build else build
    old_chunk = next((client / "_app" / "immutable" / "nodes").glob("5.*.js"))
    new_chunk = old_chunk.with_name(old_chunk.stem + "-B.js")
    old_chunk.rename(new_chunk)
    renames = {old_chunk.name: new_chunk.name}
    if realistic:
        # A real build also renames the entry file (it names the lazy chunks).
        # Without this, immutable caching would keep serving the old entry file.
        old_entry = next((client / "_app" / "immutable" / "entry").glob("app.*.js"))
        new_entry = old_entry.with_name(old_entry.stem + "-B.js")
        old_entry.rename(new_entry)
        renames[old_entry.name] = new_entry.name
    if new_version_file:
        # SvelteKit compares this file with the one the page was built with.
        version_file = client / "_app" / "version.json"
        old_version = json.loads(version_file.read_text())["version"]
        version_file.write_text(json.dumps({"version": version}))
        renames[old_version] = version
    shell = (
        build / "server" / "chunks" / "internal.js"
        if bun_build
        else build / "index.html"
    )
    scripts = [*client.rglob("*.js")]
    if bun_build:
        scripts += [build / "adapter-bun.js", *(build / "server").rglob("*.js")]
    else:
        scripts.append(shell)
    for script in scripts:
        original = script.read_text()
        body = original
        for old_name, new_name in renames.items():
            body = body.replace(old_name, new_name)
        if body != original:
            script.write_text(body)
    if retain_old_entry:
        assert realistic
        original_client = (
            server.original_build / "client" if bun_build else server.original_build
        )
        shutil.copyfile(original_client / old_entry.relative_to(client), old_entry)
        if bun_build:
            asset_table = build / "adapter-bun.js"
            table = asset_table.read_text()
            entry = next(line for line in table.splitlines() if new_entry.name in line)
            asset_table.write_text(
                table.replace(
                    entry, entry + "\n" + entry.replace(new_entry.name, old_entry.name)
                )
            )
    worker = client / "service-worker.js"
    body, count = re.subn(
        r"version:`[^`]+`", f"version:`{version}`", worker.read_text(), count=1
    )
    assert count == 1 and new_chunk.name in body
    worker.write_text(body)
    shell.write_text(shell.read_text().replace("</head>", f"<!-- {version} --></head>"))
    return build, "/" + new_chunk.relative_to(client).as_posix()


def _wait_for_waiting_worker(page) -> None:
    page.evaluate(
        "navigator.serviceWorker.getRegistration().then((registration) => "
        "(window.__appRegistration = registration))"
    )
    page.wait_for_function("window.__appRegistration?.waiting?.state === 'installed'")


@pytest.mark.all_engines
@pytest.mark.own_server
@pytest.mark.tier_core
def test_built_worker_takes_over_and_serves_a_cold_offline_deep_link(
    svelte_server, open_session, svelte_assets
):
    page = _wait_for_controlled_page(
        open_session("service-worker-shell"), svelte_server.url
    )
    expect(page.get_by_label("Room link or code")).to_be_visible()

    cache_names = _cache_names(page)
    assert len(cache_names) == 1
    assert cache_names[0].startswith(WORKER_PREFIX)
    cached_urls = set(
        page.evaluate(
            """async () => {
                const keys = await caches.keys();
                const cache = await caches.open(keys[0]);
                return (await cache.keys()).map((request) => new URL(request.url).pathname);
            }"""
        )
    )
    assert "/" in cached_urls
    assert "/robots.txt" in cached_urls
    built_assets = {
        "/" + file.relative_to(svelte_assets).as_posix()
        for file in (svelte_assets / "_app" / "immutable").rglob("*")
        if file.is_file()
    }
    assert built_assets <= cached_urls
    assert not any(path == "/api" or path.startswith("/api/") for path in cached_urls)
    assert "/sw.js" not in cached_urls
    assert WORKER_SCRIPT not in cached_urls

    worker_response = page.request.get(svelte_server.url + WORKER_SCRIPT)
    assert worker_response.status == 200
    assert "javascript" in worker_response.headers["content-type"]
    assert "<html" not in worker_response.text().lower()

    svelte_server.stop()
    page.goto(svelte_server.url + "/room/offline-shell-check")
    expect(page.get_by_text("Connect to load this room.")).to_be_visible()
    assert page.evaluate(
        """async () => {
            try {
                await fetch('/api/v1/last-room');
                return false;
            } catch {
                return true;
            }
        }"""
    )


@pytest.mark.tier_core
def test_real_build_swap_waits_for_a_stored_room_change(
    built_app_server, open_session, tmp_path
):
    server = built_app_server
    slug = "build-swap-room"
    page = _wait_for_controlled_page(
        open_session("service-worker-waiting-change"), server.url
    )
    page.evaluate(
        """async (roomSlug) => {
            const db = await new Promise((resolve, reject) => {
                const request = indexedDB.open('listr-queue', 1);
                request.onupgradeneeded = () => {
                    request.result.createObjectStore('queue', { keyPath: 'key' });
                };
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
            const tx = db.transaction('queue', 'readwrite');
            tx.objectStore('queue').put({
                key: `room:${roomSlug}`,
                entries: [{
                    opId: 'waiting-build-swap',
                    op: {
                        type: 'item.quantity_delta', list_uid: 'list-1', item_uid: 'item-1',
                        delta: 1, op_id: 'waiting-build-swap'
                    },
                    at: new Date().toISOString(), format: 1, state: 'pending'
                }]
            });
            await new Promise((resolve, reject) => {
                tx.oncomplete = resolve;
                tx.onerror = () => reject(tx.error);
                tx.onabort = () => reject(tx.error);
            });
            db.close();
        }""",
        slug,
    )
    if isinstance(server, BuiltAppServer):
        server.state.unauthorized_room = slug
    page.goto(f"{server.url}/room/{slug}")
    expect(page.get_by_text("1 change can't be sent")).to_be_visible()
    page.evaluate("window.__oldTab = true")

    cache_a = _cache_names(page)[0]
    build_b, _ = _changed_build(server, tmp_path, "test-waiting-change-B")
    server.switch_build(build_b)
    page.evaluate(
        "navigator.serviceWorker.getRegistration().then((registration) => registration.update())"
    )
    _wait_for_waiting_worker(page)
    assert "test-waiting-change-B" not in page.content()
    assert page.evaluate("window.__oldTab") is True
    assert cache_a in _cache_names(page)

    page.get_by_role("button", name="Discard all").click()
    expect(page.get_by_text("can't be sent")).to_have_count(0)
    _come_back_to_the_app(page)
    page.wait_for_function("window.__oldTab === undefined")
    page.wait_for_function(
        "document.documentElement.outerHTML.includes('test-waiting-change-B')"
    )
    assert _cache_names(page) == [f"{WORKER_PREFIX}test-waiting-change-B"]


@pytest.mark.all_engines
def test_waiting_version_takes_over_when_the_app_opens_offline(
    built_app_server, open_session, tmp_path
):

    server = built_app_server
    old_tab = _wait_for_controlled_page(
        open_session("service-worker-update"), server.url
    )
    cache_a = _cache_names(old_tab)[0]
    cache_b = f"{WORKER_PREFIX}test-update-B"

    build_b, lazy_b = _changed_build(server, tmp_path, "test-update-B")
    server.switch_build(build_b)
    old_tab.evaluate(
        "navigator.serviceWorker.getRegistration().then((registration) => registration.update())"
    )
    _wait_for_waiting_worker(old_tab)
    # The download alone changes nothing: the open tab keeps version A.
    assert set(_cache_names(old_tab)) == {cache_a, cache_b}
    assert "test-update-B" not in old_tab.content()
    old_tab.evaluate("window.__oldTab = true")

    # Opening the app switches to B, even offline: B is a complete copy.
    server.stop()
    new_tab = old_tab.context.new_page()
    # The start page: a room page would also start API requests, and WebKit
    # reports the ones the switch's reload cancels as page errors.
    new_tab.goto(server.url)
    new_tab.wait_for_function(
        "document.documentElement.outerHTML.includes('test-update-B')"
    )
    expect(new_tab.get_by_label("Room link or code")).to_be_visible()
    assert new_tab.evaluate(
        "async (url) => (await fetch(url)).headers.get('content-type')?.includes('javascript')",
        lazy_b,
    )

    # The old tab had no unsent changes, so it reloaded onto B as well.
    old_tab.wait_for_function("window.__oldTab === undefined")
    old_tab.wait_for_function(
        "document.documentElement.outerHTML.includes('test-update-B')"
    )
    new_tab.wait_for_function(
        "(expected) => caches.keys().then((names) => "
        "JSON.stringify(names) === JSON.stringify(expected))",
        arg=[cache_b],
        timeout=10_000,
    )


def _come_back_to_the_app(page) -> None:
    """What a phone does when the app returns from the background."""
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")


def test_coming_back_to_the_app_fetches_and_then_switches_version(
    built_app_server, open_session, tmp_path
):
    server = built_app_server
    page = _wait_for_controlled_page(open_session("service-worker-return"), server.url)
    build_b, _ = _changed_build(server, tmp_path, "test-return-B")
    server.switch_build(build_b)
    page.evaluate("window.__oldPage = true")

    # The first return only downloads the new version; the page stays.
    _come_back_to_the_app(page)
    _wait_for_waiting_worker(page)
    assert page.evaluate("window.__oldPage") is True

    # Typed text would be lost by a reload, so the next return keeps the page.
    field = page.get_by_label("Room link or code")
    field.fill("half-typed")
    _come_back_to_the_app(page)
    # Kept: the check is that the page does not reload. Nothing visible marks
    # a reload that did not happen, so this window is the only check.
    page.wait_for_timeout(500)
    assert page.evaluate("window.__oldPage") is True
    assert page.evaluate("window.__appRegistration.waiting?.state") == "installed"

    # With the field empty again, the next return switches to the new version.
    field.fill("")
    _come_back_to_the_app(page)
    page.wait_for_function("window.__oldPage === undefined")
    page.wait_for_function(
        "document.documentElement.outerHTML.includes('test-return-B')"
    )
    expect(page.get_by_label("Room link or code")).to_be_visible()


def test_update_keeps_versions_while_an_uncontrolled_tab_is_open(
    built_app_server, open_session, tmp_path
):
    server = built_app_server
    unclaimed_page = open_session("worker-unclaimed-tab")
    unclaimed_page.goto(server.url)
    unclaimed_page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    assert unclaimed_page.evaluate("navigator.serviceWorker.controller") is None
    cache_a = _cache_names(unclaimed_page)[0]

    context = unclaimed_page.context
    old_controlled_page = context.new_page()
    old_controlled_page.goto(server.url)
    old_controlled_page.wait_for_function(
        "navigator.serviceWorker.controller?.scriptURL.endsWith('/service-worker.js')"
    )
    build_b, _ = _changed_build(server, tmp_path, "test-unclaimed-B")
    server.switch_build(build_b)
    old_controlled_page.evaluate(
        "navigator.serviceWorker.getRegistration().then((registration) => registration.update())"
    )
    _wait_for_waiting_worker(old_controlled_page)
    cache_b = f"{WORKER_PREFIX}test-unclaimed-B"
    assert set(_cache_names(unclaimed_page)) == {cache_a, cache_b}

    old_controlled_page.close()
    unclaimed_page.wait_for_function(
        "navigator.serviceWorker.getRegistration().then((registration) => "
        "!registration.installing && !registration.waiting && "
        "registration.active?.state === 'activated')",
        timeout=20_000,
    )
    assert set(_cache_names(unclaimed_page)) == {cache_a, cache_b}

    new_page = context.new_page()
    new_page.goto(server.url)
    new_page.wait_for_function(
        "navigator.serviceWorker.controller?.scriptURL.endsWith('/service-worker.js')"
    )
    assert set(_cache_names(new_page)) == {cache_a, cache_b}

    unclaimed_page.close()
    new_page.goto(server.url)
    assert _cache_names(new_page) == [cache_b]
    server.stop()
    new_page.goto(server.url + "/room/reopened-offline")
    expect(new_page.get_by_text("Connect to load this room.")).to_be_visible()
    assert _cache_names(new_page) == [cache_b]


def test_interrupted_update_keeps_last_complete_version_usable(
    built_app_server, open_session, tmp_path
):
    server = built_app_server
    page = _wait_for_controlled_page(
        open_session("service-worker-interrupted-update"), server.url
    )
    cache_a = _cache_names(page)[0]

    build_b, asset_path = _changed_build(server, tmp_path, "test-interrupted-B")
    server.switch_build(build_b, failed_asset=asset_path)
    if isinstance(server, BunBuildServer):
        response = page.request.get(server.url + asset_path)
        assert response.status == 404
        assert "text/html" not in response.headers.get("content-type", "")
    page.evaluate(
        "navigator.serviceWorker.getRegistration().then((registration) => registration.update())"
    )

    def install_failed() -> bool:
        state = page.evaluate(
            "navigator.serviceWorker.getRegistration().then((registration) => "
            "({installing: registration.installing?.state, waiting: registration.waiting?.state}))"
        )
        return (
            (
                isinstance(server, BunBuildServer)
                or bool(server.state.failed_asset_requests)
            )
            and not state["installing"]
            and not state["waiting"]
        )

    wait_until(
        page,
        install_failed,
        "the interrupted worker install did not fail cleanly",
        timeout_ms=30_000,
    )

    if isinstance(server, BuiltAppServer):
        assert set(server.state.failed_asset_requests) == {asset_path}
    assert _cache_names(page) == [cache_a]
    server.stop()
    page.goto(server.url + "/room/last-complete-version")
    expect(page.get_by_text("Connect to load this room.")).to_be_visible()
    assert _cache_names(page) == [cache_a]


# Stale lazy chunks after a deploy (docs/offline-viewing.md) ---------------------


def _click_new_link(page, href: str) -> None:
    """Start a client-side navigation, as a click on an app link does."""
    page.evaluate(
        """(href) => {
            const link = document.createElement('a');
            link.href = href;
            link.id = 'injected-link';
            link.textContent = 'go';
            document.body.append(link);
        }""",
        href,
    )
    page.locator("#injected-link").click()


def test_failed_link_click_opens_the_link_on_the_new_build(
    built_app_server, open_session, tmp_path
):
    server = built_app_server
    page = open_session("stale-chunk", service_workers="block")
    page.goto(server.url)
    expect(page.get_by_label("Room link or code")).to_be_visible()
    assert "test-stale-B" not in page.content()

    build_b, _ = _changed_build(
        server, tmp_path, "test-stale-B", realistic=True, new_version_file=True
    )
    server.switch_build(build_b)
    page.evaluate("window.__stillOldPage = true")
    _click_new_link(page, "/list/stale-chunk")

    # The old chunk 404s; the page reloads, so the marker on `window` is gone
    # and the shell comes from build B.
    page.wait_for_function("window.__stillOldPage === undefined")
    page.wait_for_function(
        "document.documentElement.outerHTML.includes('test-stale-B')"
    )
    # The list address page of build B ran: its chunk exists and loaded.
    expect(page.get_by_text("Connect to open this saved list")).to_be_visible()


def test_unchanged_build_keeps_the_page(built_app_server, open_session):
    """No new version: nothing reloads, so the old behaviour is unchanged."""
    page = open_session("fresh-chunk", service_workers="block")
    page.goto(built_app_server.url)
    page.evaluate("window.__stillOldPage = true")
    _click_new_link(page, "/list/stale-chunk")
    expect(page.get_by_text("Connect to open this saved list")).to_be_visible()
    assert page.evaluate("window.__stillOldPage") is True


def _stale_first_page(server, open_session, tmp_path):
    """Serve build B, but answer the first page load with build A's page.

    Build A's page asks for a lazy chunk that build B no longer has, like a tab
    that was restored just before a deploy. `_app/version.json` stays the same,
    so SvelteKit's own version check stays quiet and only our handler can act.
    """
    page = open_session("preload-recovers", service_workers="block")
    old_shell = page.request.get(f"{server.url}/list/stale-chunk").body()
    build_b, _ = _changed_build(
        server, tmp_path, "test-stale-B", realistic=True, retain_old_entry=True
    )
    server.switch_build(build_b)
    page_loads = []

    def serve_page(route):
        page_loads.append(route.request.url)
        if len(page_loads) == 1:
            route.fulfill(
                body=old_shell,
                content_type="text/html",
                headers={"Cache-Control": "no-store"},
            )
        else:
            route.continue_()

    page.route("**/list/stale-chunk", serve_page)
    return page, page_loads


def test_failed_first_load_reloads_once_and_recovers(
    built_app_server, open_session, tmp_path
):
    page, page_loads = _stale_first_page(built_app_server, open_session, tmp_path)
    page.goto(f"{built_app_server.url}/list/stale-chunk")
    expect(page.get_by_text("Connect to open this saved list")).to_be_visible()
    page.wait_for_function(
        "document.documentElement.outerHTML.includes('test-stale-B')"
    )
    assert len(page_loads) == 2  # the load that failed, one reload


def test_chunk_that_stays_missing_shows_the_error_without_a_loop(
    built_app_server, open_session
):
    page = open_session("preload-loop-guard", service_workers="block")
    page_loads = []
    page.on(
        "request",
        lambda request: (
            page_loads.append(request.url) if request.is_navigation_request() else None
        ),
    )
    page.route(
        "**/_app/immutable/nodes/5.*.js",
        lambda route: route.fulfill(
            status=404,
            content_type="text/html",
            headers={"Cache-Control": "no-store"},
            body="gone",
        ),
    )
    page.goto(f"{built_app_server.url}/list/stale-chunk")
    expect(page.get_by_role("heading", name="Something went wrong")).to_be_visible()
    # Kept: the check is that no further reload starts. Nothing visible marks
    # that, so this window is the only check.
    page.wait_for_timeout(1_000)
    assert len(page_loads) == 2  # the load that failed, one reload, no more
