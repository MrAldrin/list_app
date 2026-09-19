import os
import uuid

import bcrypt
import pytest

# Set DB_PATH to memory for all tests to avoid touching the real database
os.environ["DB_PATH"] = ":memory:"
# Tests use explicit credentials, never a developer's .env or deployment secrets.
os.environ["APP_PASSWORD"] = "test-only-app-password"

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
    room_id = db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES (?, ?, ?)",
        ("Home", f"home-{str(uuid.uuid4())[:6]}", home_password_hash),
    ).lastrowid
    db.execute("INSERT INTO lists (name, room_id) VALUES ('default', ?)", (room_id,))
    db.commit()
    yield
