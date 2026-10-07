"""The Svelte shell is complete before it can serve an offline navigation.

Also: a tab from a replaced build reloads onto the new build (stale lazy chunks).
"""

import mimetypes
import re
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from conftest import ROOT
from playwright.sync_api import expect

FRONTEND_BUILD = ROOT / "frontend" / "build"
WORKER_PREFIX = "listr-app-shell-"
WORKER_SCRIPT = "/service-worker.js"


def _cache_names(page):
    return page.evaluate("caches.keys()")


def _wait_for_controlled_page(page, url: str):
    page.goto(url)
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    context = page.context
    page.close()
    page = context.new_page()
    page.goto(url)
    page.wait_for_function(
        "navigator.serviceWorker.controller?.scriptURL.endsWith('/service-worker.js')"
    )
    return page


class BuildServerState:
    build_path = FRONTEND_BUILD
    failed_asset: str | None = None
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
        self.send_header("Cache-Control", cache_control)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


class BuiltAppServer:
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


@pytest.fixture
def built_app_server(svelte_build):
    server = BuiltAppServer()
    try:
        yield server
    finally:
        server.stop()


def _changed_build(
    tmp_path, version: str, realistic: bool = False, new_version_file: bool = False
):
    """Make a second built app with distinct HTML and a real lazy chunk URL."""
    build = tmp_path / version
    shutil.copytree(FRONTEND_BUILD, build)
    old_chunk = next((build / "_app" / "immutable" / "nodes").glob("5.*.js"))
    new_chunk = old_chunk.with_name(old_chunk.stem + "-B.js")
    old_chunk.rename(new_chunk)
    renames = {old_chunk.name: new_chunk.name}
    if realistic:
        # A real build also renames the entry file (it names the lazy chunks).
        # Without this, immutable caching would keep serving the old entry file.
        old_entry = next((build / "_app" / "immutable" / "entry").glob("app.*.js"))
        new_entry = old_entry.with_name(old_entry.stem + "-B.js")
        old_entry.rename(new_entry)
        renames[old_entry.name] = new_entry.name
    if new_version_file:
        # SvelteKit compares this file with the one the page was built with.
        (build / "_app" / "version.json").write_text(f'{{"version":"{version}"}}')
    for script in [*build.rglob("*.js"), build / "index.html"]:
        body = script.read_text()
        for old_name, new_name in renames.items():
            body = body.replace(old_name, new_name)
        script.write_text(body)
    worker = build / "service-worker.js"
    body, count = re.subn(
        r"version:`[^`]+`", f"version:`{version}`", worker.read_text(), count=1
    )
    assert count == 1 and new_chunk.name in body
    worker.write_text(body)
    shell = build / "index.html"
    shell.write_text(shell.read_text().replace("</head>", f"<!-- {version} --></head>"))
    return build, "/" + new_chunk.relative_to(build).as_posix()


def _wait_for_waiting_worker(page) -> None:
    page.evaluate(
        "navigator.serviceWorker.getRegistration().then((registration) => "
        "(window.__appRegistration = registration))"
    )
    page.wait_for_function("window.__appRegistration?.waiting?.state === 'installed'")


def test_built_worker_takes_over_and_serves_a_cold_offline_deep_link(
    svelte_server, open_session
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
        "/" + file.relative_to(FRONTEND_BUILD).as_posix()
        for file in (FRONTEND_BUILD / "_app" / "immutable").rglob("*")
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


def test_waiting_update_keeps_old_tab_assets_until_safe_reopen(
    built_app_server, open_session, tmp_path
):
    server = built_app_server
    page = _wait_for_controlled_page(open_session("service-worker-update"), server.url)
    cache_a = _cache_names(page)[0]

    build_b, lazy_b = _changed_build(tmp_path, "test-update-B")
    server.state.build_path = build_b
    page.evaluate(
        "navigator.serviceWorker.getRegistration().then((registration) => registration.update())"
    )
    _wait_for_waiting_worker(page)
    cache_names = _cache_names(page)
    assert cache_a in cache_names
    assert f"{WORKER_PREFIX}test-update-B" in cache_names
    assert page.evaluate("navigator.serviceWorker.controller.scriptURL").endswith(
        WORKER_SCRIPT
    )
    assert lazy_b in page.evaluate(
        """async () => (await (await caches.open('listr-app-shell-test-update-B')).keys()).map(r => new URL(r.url).pathname)"""
    )
    # Even while B is live on the server, A's controlled navigation stays
    # paired with A's complete assets. No mixed-version HTML is served.
    page.goto(server.url + "/room/old-tab-lazy-route")
    assert "test-update-B" not in page.content()

    server.stop()
    page.goto(server.url + "/room/old-tab-lazy-route")
    expect(page.get_by_text("Connect to load this room.")).to_be_visible()
    assert cache_a in _cache_names(page)

    context = page.context
    page.close()
    server.start()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        time.sleep(0.2)
        page = context.new_page()
        page.goto(server.url)
        page.wait_for_function(
            "navigator.serviceWorker.controller?.scriptURL.endsWith('/service-worker.js')"
        )
        cache_names = _cache_names(page)
        if (
            f"{WORKER_PREFIX}test-update-B" in cache_names
            and cache_a not in cache_names
        ):
            break
        page.close()
    else:
        raise AssertionError(
            "the waiting app version was not adopted after old tabs closed"
        )

    assert "test-update-B" in page.content()
    server.stop()
    page.goto(server.url + "/room/reopened-offline")
    expect(page.get_by_text("Connect to load this room.")).to_be_visible()
    assert "test-update-B" in page.content()
    assert page.evaluate(
        "async (url) => (await fetch(url)).headers.get('content-type')?.includes('javascript')",
        lazy_b,
    )
    assert _cache_names(page) == [f"{WORKER_PREFIX}test-update-B"]


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
    server.state.build_path, _ = _changed_build(tmp_path, "test-unclaimed-B")
    old_controlled_page.evaluate(
        "navigator.serviceWorker.getRegistration().then((registration) => registration.update())"
    )
    _wait_for_waiting_worker(old_controlled_page)
    cache_b = f"{WORKER_PREFIX}test-unclaimed-B"
    assert set(_cache_names(unclaimed_page)) == {cache_a, cache_b}

    old_controlled_page.close()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        state = unclaimed_page.evaluate(
            "navigator.serviceWorker.getRegistration().then((registration) => "
            "({installing: registration.installing?.state, waiting: registration.waiting?.state, "
            "active: registration.active?.state}))"
        )
        if (
            not state["installing"]
            and not state["waiting"]
            and state["active"] == "activated"
        ):
            break
        time.sleep(0.1)
    else:
        raise AssertionError(
            "the waiting worker did not activate after its old tab closed"
        )
    assert set(_cache_names(unclaimed_page)) == {cache_a, cache_b}

    new_page = context.new_page()
    new_page.goto(server.url)
    new_page.wait_for_function(
        "navigator.serviceWorker.controller?.scriptURL.endsWith('/service-worker.js')"
    )
    assert set(_cache_names(new_page)) == {cache_a, cache_b}

    unclaimed_page.close()
    new_page.goto(server.url + "/robots.txt")
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

    server.state.build_path, asset_path = _changed_build(tmp_path, "test-interrupted-B")
    server.state.failed_asset = asset_path
    page.evaluate(
        "navigator.serviceWorker.getRegistration().then((registration) => registration.update())"
    )

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        state = page.evaluate(
            "navigator.serviceWorker.getRegistration().then((registration) => "
            "({installing: registration.installing?.state, waiting: registration.waiting?.state}))"
        )
        if (
            server.state.failed_asset_requests
            and not state["installing"]
            and not state["waiting"]
        ):
            break
        time.sleep(0.1)
    else:
        raise AssertionError("the interrupted worker install did not fail cleanly")

    assert server.state.failed_asset_requests
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

    server.state.build_path, _ = _changed_build(
        tmp_path, "test-stale-B", realistic=True, new_version_file=True
    )
    page.evaluate("window.__stillOldPage = true")
    _click_new_link(page, "/list/stale-chunk")

    # The old chunk 404s; the page reloads, so the marker on `window` is gone
    # and the shell comes from build B.
    page.wait_for_function("window.__stillOldPage === undefined")
    page.wait_for_function(
        "document.documentElement.outerHTML.includes('test-stale-B')"
    )
    # The list address page of build B ran: its chunk exists and loaded.
    expect(page.get_by_text("Could not open this list.")).to_be_visible()


def test_unchanged_build_keeps_the_page(built_app_server, open_session):
    """No new version: nothing reloads, so the old behaviour is unchanged."""
    page = open_session("fresh-chunk", service_workers="block")
    page.goto(built_app_server.url)
    page.evaluate("window.__stillOldPage = true")
    _click_new_link(page, "/create-room/some-token")
    expect(page.get_by_text("Could not check this invitation.")).to_be_visible()
    assert page.evaluate("window.__stillOldPage") is True


def _stale_first_page(server, open_session, tmp_path):
    """Serve build B, but answer the first page load with build A's page.

    Build A's page asks for a lazy chunk that build B no longer has, like a tab
    that was restored just before a deploy. `_app/version.json` stays the same,
    so SvelteKit's own version check stays quiet and only our handler can act.
    """
    build_b, _ = _changed_build(tmp_path, "test-stale-B", realistic=True)
    entry_dir = Path("_app") / "immutable" / "entry"
    for old_entry in (FRONTEND_BUILD / entry_dir).glob("app.*.js"):
        shutil.copy(old_entry, build_b / entry_dir / old_entry.name)
    server.state.build_path = build_b
    old_shell = (FRONTEND_BUILD / "index.html").read_bytes()

    page = open_session("preload-recovers", service_workers="block")
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
    expect(page.get_by_text("Could not open this list.")).to_be_visible()
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
    page.wait_for_timeout(1_000)
    assert len(page_loads) == 2  # the load that failed, one reload, no more
