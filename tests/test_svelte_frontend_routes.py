from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from svelte_frontend import DEFAULT_BUILD_DIR, register_svelte_frontend

INDEX_HTML = "<!doctype html><html><body>svelte shell</body></html>"
SECRET = "SECRET-OUTSIDE-BUILD"


@pytest.fixture
def build_dir(tmp_path: Path) -> Path:
    build = tmp_path / "build"
    (build / "_app" / "immutable" / "entry").mkdir(parents=True)
    (build / "index.html").write_text(INDEX_HTML)
    (build / "robots.txt").write_text("User-agent: *\n")
    (build / "_app" / "version.json").write_text('{"version":"1"}')
    (build / "_app" / "immutable" / "entry" / "start.abc123.js").write_text(
        "export {};"
    )
    (build / "_app" / "immutable" / "app.abc123.css").write_text("body{}")
    (tmp_path / "secret.txt").write_text(SECRET)
    (build / "link-out.txt").symlink_to(tmp_path / "secret.txt")
    return build


@pytest.fixture
def client(build_dir: Path) -> TestClient:
    app = FastAPI()
    assert register_svelte_frontend(app, build_dir)
    return TestClient(app)


def assert_index(response, cache: str = "no-cache") -> None:
    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == cache


def test_root_returns_the_page_and_never_stores_it(client):
    assert_index(client.get("/"), "no-store")


def test_page_says_links_to_other_sites_get_no_referrer(client):
    # Share and invitation addresses must not leak. Not "no-referrer": that
    # would also blank the Origin of the app's own API writes.
    response = client.get("/share/some-token")
    assert response.headers["referrer-policy"] == "same-origin"


# Decision 157: the shell at these addresses is never stored; the others only
# need a check before reuse.
NEVER_STORED = [
    "/room/home-ab12cd",
    "/room/home-ab12cd?admin=true",
    "/room/home-ab12cd/list/groceries",
    "/list/groceries",
    "/create-room/Zm9v-token_value",
]
CHECKED = ["/share/Zm9v-token_value", "/admin"]


@pytest.mark.parametrize("path", NEVER_STORED)
def test_personal_page_addresses_get_the_page_uncached(client, path):
    assert_index(client.get(path), "no-store")


@pytest.mark.parametrize("path", CHECKED)
def test_other_page_addresses_get_the_page(client, path):
    assert_index(client.get(path))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("/app", "/"),
        ("/app/", "/"),
        ("/app?room=home", "/?room=home"),
        ("/app/room/home-ab12cd", "/room/home-ab12cd"),
        ("/app/room/home-ab12cd?admin=true", "/room/home-ab12cd?admin=true"),
        ("/app/room/home-ab12cd/list/x", "/room/home-ab12cd/list/x"),
        ("/app/share/tok", "/share/tok"),
        ("/app/create-room/tok", "/create-room/tok"),
        ("/app/admin", "/admin"),
        ("/app/manifest.webmanifest", "/manifest.webmanifest"),
        ("/admin/login", "/admin"),
        ("/admin/login?x=1", "/admin?x=1"),
    ],
)
def test_old_addresses_redirect_permanently(client, old, new):
    response = client.get(old, follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"] == new


def test_old_address_redirects_also_for_head(client):
    response = client.head("/app/room/home", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"] == "/room/home"


@pytest.mark.parametrize(
    "path", ["/api/v1/nothing", "/static/nothing.png", "/static", "/api"]
)
def test_server_prefixes_are_never_the_page(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert "svelte shell" not in response.text


@pytest.mark.parametrize(
    ("path", "cache"),
    [
        ("/room/home", "no-store"),
        ("/list/groceries/", "no-store"),
        ("/x.y", "no-cache"),
    ],
)
def test_deep_links_fall_back_to_index(client, path, cache):
    assert_index(client.get(path), cache)


def test_head_request(client):
    response = client.head("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_hashed_assets_are_cached_long(client):
    response = client.get("/_app/immutable/entry/start.abc123.js")
    assert response.status_code == 200
    assert response.text == "export {};"
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["x-content-type-options"] == "nosniff"

    response = client.get("/_app/immutable/app.abc123.css")
    assert response.headers["content-type"].startswith("text/css")


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/robots.txt", "text/plain"),
        ("/_app/version.json", "application/json"),
        ("/index.html", "text/html"),
    ],
)
def test_other_files_must_revalidate(client, path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.headers["cache-control"] == "no-cache"


def test_missing_build_file_is_404_not_the_page(client):
    response = client.get("/_app/immutable/entry/missing.js")
    assert response.status_code == 404
    assert SECRET not in response.text
    assert "svelte shell" not in response.text


def test_built_service_worker_is_javascript_and_must_revalidate(client, build_dir):
    worker = build_dir / "service-worker.js"
    worker.write_text("self.addEventListener('install', () => {});")

    response = client.get("/service-worker.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"
    assert "<html" not in response.text.lower()


def test_missing_service_worker_is_404_not_the_page(client):
    response = client.get("/service-worker.js")
    assert response.status_code == 404
    assert SECRET not in response.text
    assert "svelte shell" not in response.text
    assert "<html" not in response.text.lower()


@pytest.mark.parametrize(
    "path",
    [
        "/%2e%2e/secret.txt",
        "/..%2fsecret.txt",
        "/%2e%2e%2fsecret.txt",
        "/_app/%2e%2e/%2e%2e/secret.txt",
        "/..%5csecret.txt",
        "/secret.txt%00",
    ],
)
def test_path_traversal_is_rejected(client, path):
    response = client.get(path)
    assert response.status_code == 404
    # An empty body shows our handler answered, not a default 404.
    assert response.content == b""


def test_absolute_paths_and_symlinks_never_leave_the_build(client, build_dir):
    outside = build_dir.parent / "secret.txt"
    for path in [f"/{outside}", f"//{outside}", "/link-out.txt"]:
        response = client.get(path)
        assert SECRET not in response.text
        assert_index(response, "no-cache")


def test_nothing_is_mounted_when_the_build_is_missing(tmp_path):
    app = FastAPI()
    routes_before = list(app.router.routes)
    assert not register_svelte_frontend(app, tmp_path / "no-build")
    assert app.router.routes == routes_before
    assert TestClient(app).get("/").status_code == 404


def test_folder_without_index_is_not_mounted(tmp_path):
    (tmp_path / "build").mkdir()
    assert not register_svelte_frontend(FastAPI(), tmp_path / "build")


# --- The whole app ---


REAL_INDEX = DEFAULT_BUILD_DIR / "index.html"
needs_build = pytest.mark.skipif(
    not REAL_INDEX.is_file(), reason="needs `npm run build` in frontend/"
)

PAGE_ADDRESSES = [
    "/",
    "/room/home-ab12cd",
    "/room/home-ab12cd?admin=true",
    "/list/groceries",
    "/share/some-token",
    "/admin",
    "/create-room/some-token",
]


@needs_build
@pytest.mark.parametrize("path", PAGE_ADDRESSES)
def test_real_app_answers_every_page_address_with_svelte(path):
    from main import app

    response = TestClient(app).get(path)
    assert response.status_code == 200
    assert response.text == REAL_INDEX.read_text()


@needs_build
def test_other_server_routes_still_win_over_the_page():
    from main import app

    client = TestClient(app)
    assert client.get("/manifest.json").status_code == 200
    assert client.get("/manifest.webmanifest").json()["start_url"] == "/"
    assert (
        client.get("/sw.js")
        .headers["content-type"]
        .startswith("application/javascript")
    )
    assert client.get("/static/icons/favicon-32.png").status_code == 200
    favicon = client.get("/favicon.ico")
    assert favicon.headers["content-type"] == "image/png"
    assert client.get("/api/v1/nothing").status_code == 404
    # The application's JSON API answers, not the page.
    assert (
        client.get("/api/v1/last-room")
        .headers["content-type"]
        .startswith("application/json")
    )


@needs_build
def test_page_shells_are_never_stored_but_files_are_checked():
    from main import app

    client = TestClient(app)
    for path in ("/", "/room/home", "/list/x", "/create-room/x"):
        assert client.get(path).headers["cache-control"] == "no-store"
    assert client.get("/_app/version.json").headers["cache-control"] == "no-cache"


def test_the_app_without_a_build_still_serves_the_api_and_old_routes(tmp_path):
    from server import create_app

    client = TestClient(create_app(tmp_path / "no-build"))
    assert client.get("/").status_code == 404
    assert client.get("/manifest.json").status_code == 200
    assert client.get("/sw.js").status_code == 200
    assert client.get("/api/v1/last-room").status_code == 200


def test_the_app_stops_without_a_build_when_the_build_is_required(
    tmp_path, monkeypatch
):
    from server import create_app

    monkeypatch.setenv("REQUIRE_FRONTEND_BUILD", "true")
    with pytest.raises(RuntimeError, match="Svelte build not found"):
        create_app(tmp_path / "no-build")


def test_missing_build_stops_startup_when_required(tmp_path, monkeypatch):
    monkeypatch.setenv("REQUIRE_FRONTEND_BUILD", "true")
    with pytest.raises(RuntimeError, match="Svelte build not found"):
        register_svelte_frontend(FastAPI(), tmp_path / "no-build")


def test_missing_build_is_only_logged_when_not_required(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("REQUIRE_FRONTEND_BUILD", raising=False)
    assert not register_svelte_frontend(FastAPI(), tmp_path / "no-build")
    assert "Svelte build not found" in caplog.text


def test_present_build_is_fine_when_required(build_dir, monkeypatch):
    monkeypatch.setenv("REQUIRE_FRONTEND_BUILD", "true")
    assert register_svelte_frontend(FastAPI(), build_dir)
