from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from database_crud import db, update_item_done
from item_service import add_or_restore_item


def test_simultaneous_adds_and_restores_keep_one_item():
    list_id = db.execute("SELECT id FROM lists").fetchone()[0]
    barrier = Barrier(8)

    def submit(_: int) -> str:
        barrier.wait()
        return add_or_restore_item(list_id, " Milk ")[0]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))
    assert results.count("added") == 1
    assert results.count("duplicate_active") == 7
    item_id, done = db.execute(
        "SELECT id, done FROM items WHERE list_id = ?", (list_id,)
    ).fetchone()
    assert done == 0

    update_item_done(item_id, list_id, True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))
    assert results.count("restored") == 1
    assert results.count("duplicate_active") == 7
    assert (
        db.execute(
            "SELECT COUNT(*) FROM items WHERE list_id = ?", (list_id,)
        ).fetchone()[0]
        == 1
    )
