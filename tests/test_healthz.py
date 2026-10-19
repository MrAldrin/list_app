"""GET /healthz: 200 when the database answers, 503 when it does not (src/health.py)."""

import sqlite3
from contextlib import contextmanager

import pytest
from starlette.testclient import TestClient

import health
import main
from server import create_app


@pytest.fixture
def page_client(tmp_path) -> TestClient:
    build = tmp_path / "build"
    build.mkdir()
    (build / "index.html").write_text("<!doctype html><title>ListR</title>")
    return TestClient(create_app(build))


def test_healthz_answers_ok_without_login():
    response = TestClient(main.app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["cache-control"] == "no-store"


def test_healthz_is_not_the_svelte_page(page_client):
    response = page_client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_healthz_is_503_when_the_database_fails(monkeypatch):
    @contextmanager
    def broken_transaction():
        raise sqlite3.OperationalError("disk I/O error")
        yield  # pragma: no cover

    monkeypatch.setattr(health, "transaction", broken_transaction)

    response = TestClient(main.app).get("/healthz")

    assert response.status_code == 503
    assert response.json() == {"ok": False}
