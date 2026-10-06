"""The JSON API basics: error format, no-store, request rules, room access."""

import sqlite3
from typing import Any

import pytest
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.testclient import TestClient

import database_crud
import main
from api import register_api
from api.access import room_access
from api.requests import check_write_request, json_object
from database_crud import authenticate_room_and_issue_token
from database_setup import db
from room_cookies import plain_token_cookie_name, token_cookie_name

HTTPS = "https://testserver"
SAME_ORIGIN = {"Origin": HTTPS}


def build_test_app() -> FastAPI:
    """A small app with stand-in app handlers and probe API routes."""
    app = FastAPI()

    async def page_404(request: Request, exc: Exception) -> Response:
        return HTMLResponse("app 404 page", status_code=404)

    async def page_500(request: Request, exc: Exception) -> Response:
        return HTMLResponse("app 500 page", status_code=500)

    app.add_exception_handler(404, page_404)
    app.add_exception_handler(Exception, page_500)

    @app.get("/page/boom")
    def page_boom() -> None:
        raise RuntimeError("page failure")

    register_api(app)

    probes = APIRouter(
        prefix="/api/v1/probe", dependencies=[Depends(check_write_request)]
    )

    @probes.post("/echo")
    def echo(body: dict[str, Any] = Depends(json_object)) -> dict[str, Any]:
        return body

    @probes.delete("/thing")
    def delete_thing() -> Response:
        return Response(status_code=204)

    @probes.get("/rooms/{slug}")
    def read_room(slug: str, request: Request) -> dict[str, Any]:
        with room_access(request, slug) as room:
            return {"room_id": room.room_id, "in_transaction": db.in_transaction}

    @probes.post("/rooms/{slug}/fail")
    def write_then_fail(
        slug: str, request: Request, body: dict[str, Any] = Depends(json_object)
    ) -> None:
        with room_access(request, slug, write=True) as room:
            db.execute(
                "UPDATE rooms SET name = 'changed' WHERE id = ?", (room.room_id,)
            )
            raise RuntimeError("fails after the write")

    @probes.get("/db-error")
    def db_error() -> None:
        raise sqlite3.OperationalError("database is locked")

    @probes.get("/needs-int")
    def needs_int(n: int) -> dict[str, int]:
        return {"n": n}

    app.include_router(probes)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_test_app(), base_url=HTTPS, raise_server_exceptions=False)


def room() -> tuple[int, str]:
    room_id, slug = db.execute("SELECT id, slug FROM rooms").fetchone()
    return room_id, slug


def signed_in(client: TestClient, slug: str) -> str:
    token = authenticate_room_and_issue_token(slug, "pw")[1]
    client.cookies.set(token_cookie_name(slug), token)
    return token


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


# --- Error format and no-store ---


@pytest.mark.parametrize("path", ["/api/v1/nope", "/api/v1/", "/api", "/api/v2/x"])
def test_unknown_api_paths_give_json_404(client, path):
    assert_error(client.get(path), 404, "not_found")


def test_unknown_api_path_is_404_for_writes_too(client):
    response = client.post("/api/v1/nope", json={}, headers=SAME_ORIGIN)
    assert_error(response, 404, "not_found")


def test_wrong_method_keeps_allow_header(client):
    response = client.put("/api/v1/probe/echo", json={}, headers=SAME_ORIGIN)
    assert_error(response, 405, "invalid_request")
    assert "POST" in response.headers["allow"]


def test_bad_query_parameter_is_422(client):
    assert_error(client.get("/api/v1/probe/needs-int?n=x"), 422, "invalid_request")


def test_database_error_is_503(client):
    assert_error(client.get("/api/v1/probe/db-error"), 503, "unavailable")


def test_success_responses_are_no_store(client):
    response = client.post("/api/v1/probe/echo", json={"a": 1}, headers=SAME_ORIGIN)
    assert response.status_code == 200
    assert response.json() == {"a": 1}
    assert response.headers["cache-control"] == "no-store"
    assert client.delete("/api/v1/probe/thing", headers=SAME_ORIGIN).headers[
        "cache-control"
    ] == ("no-store")


def test_other_paths_keep_their_own_error_pages(client):
    response = client.get("/somewhere-else")
    assert response.status_code == 404
    assert response.text == "app 404 page"
    assert "cache-control" not in response.headers
    response = client.get("/page/boom")
    assert response.status_code == 500
    assert response.text == "app 500 page"


def test_unhandled_api_error_is_json_without_details(client):
    response = client.post("/api/v1/probe/rooms/any/fail", json={}, headers=SAME_ORIGIN)
    # No cookie: access fails before the block runs.
    assert_error(response, 401, "not_authenticated")
    _, slug = room()
    signed_in(client, slug)
    response = client.post(
        f"/api/v1/probe/rooms/{slug}/fail", json={}, headers=SAME_ORIGIN
    )
    assert_error(response, 500, "internal_error")
    assert "fails after the write" not in response.text


# --- Same-origin and JSON rules for writes ---


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "https://evil.example"},
        {"Origin": "http://testserver"},
        {"Origin": "https://testserver.evil.example"},
        {"Origin": "null"},
        {**SAME_ORIGIN, "Sec-Fetch-Site": "cross-site"},
        {**SAME_ORIGIN, "Sec-Fetch-Site": "same-site"},
        {**SAME_ORIGIN, "Sec-Fetch-Site": "none"},
    ],
)
def test_writes_need_the_same_origin(client, headers):
    assert_error(
        client.post("/api/v1/probe/echo", json={}, headers=headers),
        403,
        "forbidden_origin",
    )
    assert_error(
        client.delete("/api/v1/probe/thing", headers=headers), 403, "forbidden_origin"
    )


def test_same_origin_with_sec_fetch_site_is_accepted(client):
    headers = {**SAME_ORIGIN, "Sec-Fetch-Site": "same-origin"}
    assert client.post("/api/v1/probe/echo", json={}, headers=headers).json() == {}


def test_plain_http_same_origin_is_accepted():
    client = TestClient(build_test_app(), base_url="http://192.168.1.5:8080")
    response = client.post(
        "/api/v1/probe/echo", json={}, headers={"Origin": "http://192.168.1.5:8080"}
    )
    assert response.status_code == 200


def test_reads_do_not_need_an_origin(client):
    _, slug = room()
    signed_in(client, slug)
    assert client.get(f"/api/v1/probe/rooms/{slug}").status_code == 200


@pytest.mark.parametrize(
    "content_type", [None, "text/plain", "application/x-www-form-urlencoded"]
)
def test_writes_need_a_json_content_type(client, content_type):
    headers = dict(SAME_ORIGIN)
    if content_type:
        headers["Content-Type"] = content_type
    response = client.post("/api/v1/probe/echo", content=b"{}", headers=headers)
    assert_error(response, 415, "invalid_request")


def test_json_content_type_with_charset_is_accepted(client):
    headers = {**SAME_ORIGIN, "Content-Type": "application/json; charset=utf-8"}
    response = client.post("/api/v1/probe/echo", content=b'{"a": 1}', headers=headers)
    assert response.json() == {"a": 1}


def test_delete_with_a_non_json_body_is_415(client):
    headers = {**SAME_ORIGIN, "Content-Type": "text/plain"}
    response = client.request(
        "DELETE", "/api/v1/probe/thing", content=b"x", headers=headers
    )
    assert_error(response, 415, "invalid_request")


def test_origin_is_checked_before_the_content_type(client):
    response = client.post(
        "/api/v1/probe/echo", content=b"x", headers={"Origin": "https://evil.example"}
    )
    assert_error(response, 403, "forbidden_origin")


@pytest.mark.parametrize(
    ("body", "status"), [(b"{not json", 400), (b"\xff", 400), (b"[1, 2]", 422)]
)
def test_body_must_be_a_json_object(client, body, status):
    headers = {**SAME_ORIGIN, "Content-Type": "application/json"}
    response = client.post("/api/v1/probe/echo", content=body, headers=headers)
    assert_error(response, status, "invalid_request")


def test_large_body_is_rejected(client):
    headers = {**SAME_ORIGIN, "Content-Type": "application/json"}
    body = b'{"a": "' + b"x" * 70_000 + b'"}'
    response = client.post("/api/v1/probe/echo", content=body, headers=headers)
    assert_error(response, 413, "invalid_request")


# --- Room access helper ---


def test_room_access_runs_in_one_transaction(client):
    room_id, slug = room()
    signed_in(client, slug)
    response = client.get(f"/api/v1/probe/rooms/{slug}")
    assert response.json() == {"room_id": room_id, "in_transaction": True}
    assert not db.in_transaction


def test_room_access_rolls_back_on_error(client):
    _, slug = room()
    signed_in(client, slug)
    client.post(f"/api/v1/probe/rooms/{slug}/fail", json={}, headers=SAME_ORIGIN)
    assert db.execute("SELECT name FROM rooms").fetchone()[0] == "Home"
    assert not db.in_transaction


@pytest.mark.parametrize("token", ["wrong-token", "x" * 300])
def test_room_access_rejects_bad_tokens(client, token):
    _, slug = room()
    client.cookies.set(token_cookie_name(slug), token)
    assert_error(client.get(f"/api/v1/probe/rooms/{slug}"), 401, "not_authenticated")


def test_unknown_room_looks_like_no_access(client):
    _, slug = room()
    unknown = client.get("/api/v1/probe/rooms/no-such-room")
    no_access = client.get(f"/api/v1/probe/rooms/{slug}")
    assert_error(unknown, 401, "not_authenticated")
    assert unknown.json() == no_access.json()


def test_token_of_another_room_is_rejected(client):
    _, slug = room()
    _, other_slug = database_crud.create_room("Other", "other-pw")
    token = authenticate_room_and_issue_token(other_slug, "other-pw")[1]
    client.cookies.set(token_cookie_name(slug), token)
    assert_error(client.get(f"/api/v1/probe/rooms/{slug}"), 401, "not_authenticated")


def test_https_reads_only_the_host_cookie(client):
    _, slug = room()
    token = authenticate_room_and_issue_token(slug, "pw")[1]
    client.cookies.set(plain_token_cookie_name(slug), token)
    assert_error(client.get(f"/api/v1/probe/rooms/{slug}"), 401, "not_authenticated")


def test_plain_http_reads_only_the_plain_cookie():
    client = TestClient(build_test_app(), base_url="http://testserver")
    _, slug = room()
    token = authenticate_room_and_issue_token(slug, "pw")[1]
    client.cookies.set(token_cookie_name(slug), token)
    assert client.get(f"/api/v1/probe/rooms/{slug}").status_code == 401
    client.cookies.clear()
    client.cookies.set(plain_token_cookie_name(slug), token)
    assert client.get(f"/api/v1/probe/rooms/{slug}").status_code == 200


def test_database_error_during_access_check_is_503(client, monkeypatch):
    _, slug = room()
    signed_in(client, slug)

    def locked(*args: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(database_crud, "_valid_room_id_for_token_locked", locked)
    assert_error(client.get(f"/api/v1/probe/rooms/{slug}"), 503, "unavailable")
    assert not db.in_transaction


# --- The real app ---


def test_real_app_serves_json_404_under_api():
    client = TestClient(main.app)
    assert_error(client.get("/api/v1/does-not-exist"), 404, "not_found")


def test_real_app_keeps_html_errors_off_the_api_and_json_errors_on_it():
    # Every kind of error has a handler that answers JSON under /api and leaves
    # other addresses to FastAPI's defaults.
    assert 404 in main.app.exception_handlers
    assert StarletteHTTPException in main.app.exception_handlers
    assert Exception in main.app.exception_handlers
    client = TestClient(main.app, base_url=HTTPS)
    response = client.get("/api/v1/last-room/extra")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"


def test_real_app_has_no_docs_or_openapi_pages():
    client = TestClient(main.app, base_url=HTTPS)
    for path in ("/docs", "/redoc", "/openapi.json"):
        response = client.get(path)
        assert "swagger" not in response.text.lower()
        assert '"openapi"' not in response.text
