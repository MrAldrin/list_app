from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.routing import Match
from starlette.testclient import TestClient

from svelte_frontend import register_svelte_frontend

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


def assert_index(response) -> None:
    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"


def test_app_root_returns_the_page(client):
    assert_index(client.get("/app/"))


def test_app_without_slash_redirects(client):
    response = client.get("/app", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/app/"

    response = client.get("/app?room=home", follow_redirects=False)
    assert response.headers["location"] == "/app/?room=home"


@pytest.mark.parametrize("path", ["/app/room/home", "/app/list/groceries/", "/app/x.y"])
def test_deep_links_fall_back_to_index(client, path):
    assert_index(client.get(path))


def test_head_request(client):
    response = client.head("/app/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_hashed_assets_are_cached_long(client):
    response = client.get("/app/_app/immutable/entry/start.abc123.js")
    assert response.status_code == 200
    assert response.text == "export {};"
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["x-content-type-options"] == "nosniff"

    response = client.get("/app/_app/immutable/app.abc123.css")
    assert response.headers["content-type"].startswith("text/css")


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/app/robots.txt", "text/plain"),
        ("/app/_app/version.json", "application/json"),
        ("/app/index.html", "text/html"),
    ],
)
def test_other_files_must_revalidate(client, path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.headers["cache-control"] == "no-cache"


def test_missing_build_file_is_404_not_the_page(client):
    response = client.get("/app/_app/immutable/entry/missing.js")
    assert response.status_code == 404
    assert SECRET not in response.text
    assert "svelte shell" not in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/app/%2e%2e/secret.txt",
        "/app/..%2fsecret.txt",
        "/app/%2e%2e%2fsecret.txt",
        "/app/_app/%2e%2e/%2e%2e/secret.txt",
        "/app/..%5csecret.txt",
        "/app/secret.txt%00",
    ],
)
def test_path_traversal_is_rejected(client, path):
    response = client.get(path)
    assert response.status_code == 404
    # An empty body shows our handler answered, not a default 404.
    assert response.content == b""


def test_absolute_paths_and_symlinks_never_leave_the_build(client, build_dir):
    outside = build_dir.parent / "secret.txt"
    for path in [f"/app/{outside}", f"/app//{outside}", "/app/link-out.txt"]:
        response = client.get(path)
        assert SECRET not in response.text
        assert_index(response)


def test_nothing_is_mounted_when_the_build_is_missing(tmp_path):
    app = FastAPI()
    routes_before = list(app.router.routes)
    assert not register_svelte_frontend(app, tmp_path / "no-build")
    assert app.router.routes == routes_before
    assert TestClient(app).get("/app/").status_code == 404


def test_folder_without_index_is_not_mounted(tmp_path):
    (tmp_path / "build").mkdir()
    assert not register_svelte_frontend(FastAPI(), tmp_path / "build")


# --- Together with the NiceGUI app ---


@pytest.fixture
def nicegui_app(build_dir):
    """The real NiceGUI app, with the temporary build's routes put first."""
    from main import app

    original = list(app.router.routes)
    register_svelte_frontend(app, build_dir)
    added = app.router.routes[len(original) :]
    app.router.routes[:] = [*added, *original]
    try:
        yield app
    finally:
        app.router.routes[:] = original


def first_route(app, path: str):
    scope = {"type": "http", "path": path, "method": "GET", "root_path": ""}
    for route in app.router.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route
    return None


def test_root_is_still_the_nicegui_page(nicegui_app):
    route = first_route(nicegui_app, "/")
    assert route is not None
    assert (route.path, route.name) == ("/", "index")
    for path in ["/room/home", "/list/groceries", "/admin", "/static/sw.js"]:
        assert not first_route(nicegui_app, path).path.startswith("/app")


def test_app_is_served_through_the_nicegui_middleware(nicegui_app):
    client = TestClient(nicegui_app)
    assert_index(client.get("/app/"))
    assert_index(client.get("/app/room/home"))
    response = client.get("/app/_app/immutable/entry/start.abc123.js")
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    # The app's own middleware runs for /app/ too, and other routes still work.
    assert client.get("/manifest.json").status_code == 200


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
