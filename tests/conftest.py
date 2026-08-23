import os

import pytest

# Set DB_PATH to memory for all tests to avoid touching the real database
os.environ["DB_PATH"] = ":memory:"

from database_crud import create_room
from database_setup import db


@pytest.fixture(autouse=True)
def clean_db():
    # Clear tables before each test to ensure isolation
    db.execute("DELETE FROM items")
    db.execute("DELETE FROM lists")
    db.execute("DELETE FROM rooms")
    room_id, _ = create_room("Home", "pw")
    db.execute("INSERT INTO lists (name, room_id) VALUES ('default', ?)", (room_id,))
    db.commit()
    yield
