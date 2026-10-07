"""Every API response names the API version; the frontend expects the same one."""

import re
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute
from starlette.testclient import TestClient

import main
from api import build_router
from api.version import API_VERSION, API_VERSION_HEADER

HTTPS = "https://testserver"
COMPAT_FILE = (
    Path(__file__).resolve().parents[1] / "frontend/src/lib/data/compat.svelte.ts"
)


def _walk(router: APIRouter, prefix: str) -> list[tuple[str, str]]:
    """Every (method, path) of a router. FastAPI keeps included routers nested."""
    found = []
    for route in router.routes:
        if isinstance(route, APIRoute):
            found.extend(
                (method, prefix + route.path) for method in sorted(route.methods)
            )
        else:  # an included router (a FastAPI detail, so the test fails loudly)
            nested = route.include_context  # type: ignore[attr-defined]
            found.extend(
                _walk(route.original_router, prefix + nested.prefix)  # type: ignore[attr-defined]
            )
    return found


def api_routes() -> list[tuple[str, str]]:
    paths = _walk(build_router(), "")
    return [(method, re.sub(r"\{[^}]+\}", "unknown", path)) for method, path in paths]


@pytest.fixture
def client() -> TestClient:
    return TestClient(
        main.app,
        base_url=HTTPS,
        headers={"Origin": HTTPS},
        raise_server_exceptions=False,
    )


def test_the_route_list_is_not_empty() -> None:
    # A guard for the test below: it must really visit routes.
    assert len(api_routes()) > 20


@pytest.mark.parametrize(("method", "path"), api_routes())
def test_every_api_route_sends_the_version(
    client: TestClient, method: str, path: str
) -> None:
    # No sign-in and no body: most answers are errors, and errors count too.
    response = client.request(method, path, json={} if method != "GET" else None)
    assert response.headers[API_VERSION_HEADER] == str(API_VERSION)


def test_unknown_api_paths_and_wrong_methods_send_the_version(
    client: TestClient,
) -> None:
    assert client.get("/api/v1/nothing-here").headers[API_VERSION_HEADER] == str(
        API_VERSION
    )
    assert client.put("/api/v1/last-room").headers[API_VERSION_HEADER] == str(
        API_VERSION
    )


def test_pages_do_not_send_the_version(client: TestClient) -> None:
    assert API_VERSION_HEADER not in client.get("/manifest.json").headers


def test_frontend_expects_the_same_version() -> None:
    match = re.search(r"EXPECTED_API_VERSION\s*=\s*(\d+)", COMPAT_FILE.read_text())
    assert match, "frontend compat.ts must define EXPECTED_API_VERSION"
    assert int(match.group(1)) == API_VERSION
