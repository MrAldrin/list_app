import os
import uuid

import bcrypt
import pytest

# Set DB_PATH to memory for all tests to avoid touching the real database
os.environ["DB_PATH"] = ":memory:"
# Tests use explicit credentials, never a developer's .env or deployment secrets.
os.environ["APP_PASSWORD"] = "test-only-app-password"

from fastapi import FastAPI

from api import register_api
from database_setup import db


@pytest.fixture(scope="session")
def home_password_hash():
    # Reuse only the expensive hash, never mutable database state.
    # Keep bcrypt's production-default cost; room-creation tests still hash normally.
    return bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode("utf-8")


@pytest.fixture(autouse=True)
def clean_db(home_password_hash):
    # Clear tables before each test to ensure isolation
    db.execute("DELETE FROM room_invitations")
    db.execute("DELETE FROM items")
    db.execute("DELETE FROM lists")
    db.execute("DELETE FROM room_access_tokens")
    db.execute("DELETE FROM rooms")
    # Room deletes cascade to these; clear them anyway in case a test left
    # rows behind with foreign keys off.
    db.execute("DELETE FROM deletions")
    db.execute("DELETE FROM processed_ops")
    room_id = db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
        ("Home", f"home-{str(uuid.uuid4())[:6]}", home_password_hash),
    ).lastrowid
    db.execute(
        "INSERT INTO lists (name, slug, room_id, share_token) "
        "VALUES ('default', ?, ?, ?)",
        (f"default-{str(uuid.uuid4())[:6]}", room_id, str(uuid.uuid4())),
    )
    db.commit()
    yield


@pytest.fixture
def without_field_rules():
    """Drop the migration 6 guards, so a test can store old, odd values."""
    guards = db.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type = 'trigger' AND name LIKE '%_field_rules_%'"
    ).fetchall()
    assert guards
    for name, _sql in guards:
        db.execute(f"DROP TRIGGER {name}")
    db.commit()
    yield
    db.rollback()
    for _name, sql in guards:
        db.execute(sql)
    db.commit()


# Admin API tests (tests/api_helpers.py, "Admin"): the API router alone, with no
# A session middleware. Admin sign-in has its own cookie and must not
# depend on it (decision 144).
@pytest.fixture(scope="module")
def admin_app() -> FastAPI:
    test_app = FastAPI()
    register_api(test_app)
    return test_app
