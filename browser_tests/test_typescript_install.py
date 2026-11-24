"""Install and health contracts against the real Bun build, without a browser."""

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import httpx2 as httpx
import pytest

from conftest import ROOT, TS_ENTRY, TypeScriptTestServer

pytestmark = pytest.mark.usefixtures("typescript_only")


@pytest.fixture
def typescript_only(pytestconfig: pytest.Config) -> None:
    if pytestconfig.getoption("--browser-backend") != "typescript":
        pytest.skip("Run with --browser-backend typescript after bun run build:ts")


@pytest.fixture
def client(server):
    with httpx.Client(base_url=server.url) as client:
        yield client


def assert_security(response: httpx.Response) -> None:
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["content-security-policy"] == "frame-ancestors 'none'"


def test_manifest_aliases_are_public_and_only_change_the_start_url(client) -> None:
    cache = "no-cache, no-store, must-revalidate"
    default = None
    for path in ("/manifest.webmanifest", "/manifest.json", "/static/manifest.json"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/manifest+json"
        assert response.headers["cache-control"] == cache
        assert_security(response)
        manifest = response.json()
        assert (manifest["id"], manifest["scope"], manifest["start_url"]) == (
            "/",
            "/",
            "/",
        )
        if default is None:
            default = manifest
        assert manifest == default

    for slug in ("unknown-room", "room%22%3F%3E%3C%26%20%23", "a%2Fb"):
        for suffix in ("json", "webmanifest"):
            path = f"/room-manifest/{slug}.{suffix}?admin=true&password=secret"
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/manifest+json"
            assert response.headers["cache-control"] == cache
            assert response.json() == {**default, "start_url": f"/room/{slug}"}

    for icon in default["icons"]:
        response = client.get(icon["src"])
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize(
    ("alias", "original"),
    [
        ("/apple-touch-icon.png", "/static/icons/apple-touch-icon.png"),
        ("/apple-touch-icon-precomposed.png", "/static/icons/apple-touch-icon.png"),
        ("/favicon.ico", "/static/icons/favicon-32.png"),
    ],
)
def test_icon_aliases_serve_the_same_png(client, alias: str, original: str) -> None:
    response = client.get(alias)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert response.content == client.get(original).content
    assert_security(response)


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("/app", "/"),
        ("/app/", "/"),
        ("/app?add", "/?add"),
        (
            "/app/room/test/list/groceries?admin=true&name=a%20b",
            "/room/test/list/groceries?admin=true&name=a%20b",
        ),
        ("/app/share/token", "/share/token"),
        ("/app/create-room/token", "/create-room/token"),
        ("/app/manifest.webmanifest", "/manifest.webmanifest"),
        ("/app//another-host.invalid/path", "/another-host.invalid/path"),
        ("/admin/login?source=old", "/admin?source=old"),
    ],
)
def test_old_addresses_redirect_permanently(
    client, method: str, old: str, new: str
) -> None:
    response = client.request(method, old)
    assert response.status_code == 308
    assert response.headers["location"] == new
    assert response.content == b""
    assert_security(response)


@pytest.mark.parametrize(
    ("path", "cache"),
    [
        ("/", "no-store"),
        ("/room/test?admin=true", "no-store"),
        ("/room/test/list/groceries", "no-store"),
        ("/list/groceries", "no-store"),
        ("/create-room/token", "no-store"),
        ("/share/token", "no-cache"),
        ("/admin", "no-cache"),
    ],
)
def test_page_shell_headers(client, path: str, cache: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == cache
    assert response.headers["referrer-policy"] == "same-origin"
    assert_security(response)
    head = client.head(path)
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["cache-control"] == cache
    assert head.headers["referrer-policy"] == "same-origin"
    assert_security(head)


def test_workers_and_assets_do_not_answer_with_the_page(
    client, server, svelte_assets
) -> None:
    script = client.get("/sw.js")
    head = client.head("/sw.js")
    for response in (script, head):
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/javascript"
        assert response.headers["cache-control"] == "no-store"
        assert_security(response)
    assert head.content == b""
    assert "registration.unregister" in script.text
    assert "respondWith" not in script.text and "<html" not in script.text.lower()
    assert (
        client.post("/sw.js", headers={"Origin": server.url}).headers["allow"]
        == "GET, HEAD"
    )
    assert client.post("/sw.js").status_code == 403

    asset = next((svelte_assets / "_app" / "immutable" / "entry").glob("app.*.js"))
    hashed_url = "/" + asset.relative_to(svelte_assets).as_posix()
    for path, cache, media in (
        ("/service-worker.js", "no-cache", "javascript"),
        ("/robots.txt", "no-cache", "text/plain"),
        ("/_app/version.json", "no-cache", "application/json"),
        (hashed_url, "public, max-age=31536000, immutable", "javascript"),
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == cache
        assert media in response.headers["content-type"]
        assert_security(response)
        head = client.head(path)
        assert head.status_code == 200
        assert head.content == b""
        assert head.headers["cache-control"] == cache
        assert_security(head)
        unchanged = client.get(
            path, headers={"If-None-Match": response.headers["etag"]}
        )
        assert unchanged.status_code == 304
        assert_security(unchanged)

    for path in (
        "/_app/immutable/missing.js",
        "/static",
        "/static/sw.js",
        "/room-manifest/missing.txt",
    ):
        response = client.get(path)
        assert response.status_code == 404
        assert "text/html" not in response.headers.get("content-type", "")
        assert_security(response)
    for path in ("/api", "/api/v1/nothing"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
        assert_security(response)


def test_missing_worker_is_not_html(tmp_path: Path) -> None:
    build = shutil.copytree(TS_ENTRY.parent, tmp_path / "build-ts")
    (tmp_path / "node_modules").symlink_to(
        ROOT / "frontend" / "node_modules", target_is_directory=True
    )
    assets = build / "client"
    (assets / "service-worker.js").unlink()
    missing_chunk = next((assets / "_app" / "immutable" / "entry").glob("app.*.js"))
    missing_chunk.unlink()
    server = TypeScriptTestServer(tmp_path, entry=build / "index.js")
    try:
        server.start()
        for method in ("GET", "HEAD"):
            response = httpx.request(method, server.url + "/service-worker.js")
            assert response.status_code == 404
            assert "text/html" not in response.headers.get("content-type", "")
            assert_security(response)
            asset = httpx.request(
                method, server.url + "/" + missing_chunk.relative_to(assets).as_posix()
            )
            assert asset.status_code == 404
            assert "text/html" not in asset.headers.get("content-type", "")
            assert_security(asset)
            legacy = httpx.request(method, server.url + "/sw.js")
            assert legacy.status_code == 200
            assert legacy.headers["content-type"] == "application/javascript"
            assert legacy.headers["cache-control"] == "no-store"
    finally:
        server.stop()


@pytest.mark.own_server
def test_health_checks_the_database_and_never_returns_app_html(client, server) -> None:
    def check(status: int, ok: bool) -> None:
        response = client.get("/healthz")
        assert response.status_code == status
        assert response.json() == {"ok": ok}
        assert response.headers["content-type"].startswith("application/json")
        assert response.headers["cache-control"] == "no-store"
        assert_security(response)

    check(200, True)
    with closing(sqlite3.connect(server.database)) as db:
        db.execute("ALTER TABLE rooms RENAME TO rooms_unavailable")
    check(503, False)
    assert client.head("/healthz").status_code == 405
