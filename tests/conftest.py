import os
import pytest

# Set DB_PATH to memory for all tests to avoid touching the real database
os.environ["DB_PATH"] = ":memory:"

from database_setup import db

@pytest.fixture(autouse=True)
def clean_db():
    # Clear tables before each test to ensure isolation
    db.execute("DELETE FROM items")
    db.execute("DELETE FROM lists")
    # Re-insert the "default" list that database_setup.py normally creates
    db.execute("INSERT INTO lists (name) VALUES ('default')")
    db.commit()
    yield
