"""Check a current real build; preserve Python-only runs without a build."""

import fcntl
import os
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import pytest
from starlette.testclient import TestClient

from server import create_app
from svelte_frontend import DEFAULT_BUILD_DIR


class ShellHead(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_head = False
        self.icons: list[str | None] = []
        self.capable: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "head":
            self.in_head = True
        if not self.in_head:
            return
        if tag == "link" and "apple-touch-icon" in (values.get("rel") or "").split():
            self.icons.append(values.get("href"))
        if tag == "meta" and values.get("name") == "apple-mobile-web-app-capable":
            self.capable.append(values.get("content"))

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self.in_head = False


BUILD_INDEX = DEFAULT_BUILD_DIR / "index.html"
# Match the optional real-build route checks. A missing build is not a product
# failure; once a build exists, stale source must never use the old artifact.
needs_build = pytest.mark.skipif(
    not BUILD_INDEX.is_file(), reason="needs `bun run build` in frontend/"
)


@pytest.fixture(scope="module")
def current_build(tmp_path_factory: pytest.TempPathFactory) -> Path:
    frontend = DEFAULT_BUILD_DIR.parent
    inputs = (
        "src",
        "static",
        "package.json",
        "bun.lock",
        "vite.config.ts",
        "tsconfig.json",
    )
    shared = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        shared = shared.parent
    with (shared / "svelte-build-contract.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        newest = max(
            file.stat().st_mtime_ns
            for name in inputs
            for path in [frontend / name]
            for file in (path.rglob("*") if path.is_dir() else [path])
            if file.is_file()
        )
        if not BUILD_INDEX.is_file() or BUILD_INDEX.stat().st_mtime_ns < newest:
            bun = shutil.which("bun")
            assert bun is not None, (
                "Stale frontend build: install Bun or run `bun run build` first"
            )
            print("Refreshing the real frontend build (bun run build)")
            result = subprocess.run(
                [bun, "run", "build"],
                cwd=frontend,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            assert BUILD_INDEX.is_file(), (
                "Build did not produce frontend/build/index.html"
            )
    return BUILD_INDEX


@needs_build
def test_built_shell_declares_home_screen_icon(current_build: Path) -> None:
    head = ShellHead()
    head.feed(current_build.read_text(encoding="utf-8"))
    assert len(head.icons) == 1
    assert head.icons[0]
    icon_url = urljoin("https://testserver/room/home-ab12cd", head.icons[0])
    assert icon_url == "https://testserver/static/icons/apple-touch-icon.png"
    assert head.capable == ["yes"]
    client = TestClient(
        create_app(build_dir=DEFAULT_BUILD_DIR), base_url="https://testserver"
    )
    response = client.get(icon_url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
