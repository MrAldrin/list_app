"""Migration 14: stored tag settings keep existing lists as they were."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from migration_helpers import migrate_to

from database_setup import _migrations
from migrations import run_migrations


def _insert_list(db: sqlite3.Connection, room_id: int, slug: str) -> int:
    return db.execute(
        "INSERT INTO lists (name, slug, room_id, share_token) VALUES (?, ?, ?, ?)",
        ("Shop", slug, room_id, f"token-{slug}"),
    ).lastrowid


def test_upgrade_gives_existing_lists_the_old_behavior(tmp_path: Path) -> None:
    with closing(sqlite3.connect(tmp_path / "old.db")) as db, db:
        migrate_to(db, 13)
        room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
        list_id = _insert_list(db, room_id, "shop")
        db.execute("UPDATE lists SET list_tags = '[\"Lidl\"]' WHERE id = ?", (list_id,))
        db.commit()
        before_seq = db.execute("SELECT change_seq FROM rooms").fetchone()[0]

        run_migrations(db, _migrations("pw"))

        assert db.execute(
            "SELECT tag_mode, tag_show_on_items, tag_only_item_tags, tag_colors "
            "FROM lists WHERE id = ?",
            (list_id,),
        ).fetchone() == ("multi", 1, 0, "{}")
        assert db.execute("SELECT change_seq FROM rooms").fetchone()[0] == before_seq


def test_settings_changes_bump_the_list_change_seq(tmp_path: Path) -> None:
    with closing(sqlite3.connect(tmp_path / "new.db")) as db, db:
        run_migrations(db, _migrations("pw"))
        room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
        list_id = _insert_list(db, room_id, "shop")
        seq = db.execute("SELECT change_seq FROM rooms").fetchone()[0]

        db.execute(
            "UPDATE lists SET tag_mode = 'single', tag_colors = '{\"Lidl\": 6}' "
            "WHERE id = ?",
            (list_id,),
        )

        assert db.execute("SELECT change_seq FROM rooms").fetchone()[0] == seq + 1
        assert (
            db.execute(
                "SELECT changed_seq FROM lists WHERE id = ?", (list_id,)
            ).fetchone()[0]
            == seq + 1
        )


@pytest.mark.parametrize(
    "update",
    [
        "tag_mode = 'many'",
        "tag_show_on_items = 2",
        "tag_only_item_tags = 'yes'",
        "tag_colors = '[]'",
        "tag_colors = 'not json'",
        "tag_colors = '{\"Lidl\": 7}'",
        "tag_colors = '{\"Lidl\": -1}'",
        'tag_colors = \'{"Lidl": "red"}\'',
    ],
)
def test_bad_tag_settings_are_rejected(tmp_path: Path, update: str) -> None:
    with closing(sqlite3.connect(tmp_path / "guard.db")) as db, db:
        run_migrations(db, _migrations("pw"))
        room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
        list_id = _insert_list(db, room_id, "shop")
        with pytest.raises(sqlite3.IntegrityError, match="tag setting"):
            db.execute(f"UPDATE lists SET {update} WHERE id = ?", (list_id,))
        with pytest.raises(sqlite3.IntegrityError, match="tag setting"):
            db.execute(
                "INSERT INTO lists (name, slug, room_id, share_token, "
                f"{update.split(' = ')[0]}) VALUES ('Bad', 'bad', ?, 'x', "
                f"{update.split(' = ', 1)[1]})",
                (room_id,),
            )


def test_tag_colors_accept_every_color_from_0_to_6(tmp_path: Path) -> None:
    with closing(sqlite3.connect(tmp_path / "colors.db")) as db, db:
        run_migrations(db, _migrations("pw"))
        room_id = db.execute("SELECT id FROM rooms").fetchone()[0]
        list_id = _insert_list(db, room_id, "shop")
        db.execute(
            'UPDATE lists SET tag_colors = \'{"a": 0, "b": 6}\' WHERE id = ?',
            (list_id,),
        )
        assert db.execute(
            "SELECT tag_colors FROM lists WHERE id = ?", (list_id,)
        ).fetchone() == ('{"a": 0, "b": 6}',)
