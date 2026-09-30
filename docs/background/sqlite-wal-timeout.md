# SQLite WAL mode and lock-wait timeout: findings

Investigation for the backlog item "[data] Evaluate WAL mode and explicitly set
and document SQLite's lock-wait timeout" (`plans/backlog.md`). Measured locally
on 2026-09-30 with Python 3.13 and SQLite 3.50.4 on disposable databases.
Production was not touched.

## Recommendation

- **Keep WAL off** (keep SQLite's default rollback journal).
- **Set the lock-wait timeout explicitly to 1 second** instead of relying on
  Python's hidden 5-second default.

## Background in plain words

- **Journal mode** is how SQLite keeps a write safe if the app crashes halfway.
  The default *rollback journal* writes into the database file and keeps an undo
  copy on the side. *WAL* (write-ahead log) writes changes to a separate
  `list.db-wal` file and merges them in later.
- The practical difference is **locking**. With a rollback journal, a write
  cannot finish while someone else is reading. With WAL, readers and one writer
  can work at the same time.
- The **lock-wait timeout** (`busy_timeout`) is how long a connection waits for
  someone else's lock before it gives up with `database is locked`.

## How the app uses SQLite today

- `src/database_setup.py` opens one connection with `sqlite3.connect(path,
  check_same_thread=False)`. Measured: journal mode `delete` (rollback journal)
  and `busy_timeout` 5000 ms (Python's default `timeout=5.0`).
- All app queries share that one connection behind `_DB_LOCK`, and Railway runs
  one instance. So the app never waits on itself.
- The only other connection is the **deploy backup** (`scripts/deploy_backup.py`),
  a read-only backup-API copy run at deploy time. The pre-migration copy in
  `src/migrations.py` uses the app's own connection, so it does not contend.
- Database calls run on NiceGUI's event loop. **While a write waits for a lock,
  the whole app is frozen for every user**, not only for that request.
- Production is about 100 KB (the two local deploy backups are 102,400 bytes).

## Measurements

| Test | Rollback journal (today) | WAL |
| --- | --- | --- |
| Backup-API copy, ~100 KB database | 22 ms | 20 ms |
| Backup-API copy, 2.4 MB (30,000 items) | 41 ms | 41 ms |
| App write while a reader holds a read lock for 0.5 s, timeout 5 s | waits 0.55 s, then succeeds | — |
| App write while a reader holds a read lock for 2 s, timeout 1 s | `database is locked` after 1.00 s | succeeds in 0.01 s |
| App write while a reader holds a read lock, timeout 0 | fails at once | — |
| 5 backups (2.4 MB) during steady app writes | all intact and consistent; slowest write 74 ms | all intact and consistent; slowest write 12–16 ms |
| Read-only (`mode=ro`) open with the app running | works | works |
| `mode=ro` open, app stopped, no sidecar files, read-only folder | works | fails: `attempt to write a readonly database` |
| Journal mode of a backup-API copy | rollback | **WAL** (copy inherits it) |
| `mode=ro` check of that copy (as `verify_local_backup` does) | no extra files | leaves `-wal` and `-shm` files in the backup folder |
| WAL file size after 5,000 small writes | — | 4.1 MB; it stays, it does not shrink by itself |

## Why WAL is not worth it here

- **The benefit is tiny.** WAL only helps when another connection reads while
  the app writes. Here that is one backup a few times a week, lasting about
  20 ms. At worst, a user's write waits about 20–70 ms.
- **It adds costs:**
  - Two extra files (`-wal`, `-shm`) to keep together in restores and manual copies.
  - Backup copies become WAL files. The deploy script's local check would leave
    `-wal`/`-shm` files in the backup folder, and `older_backups()` would not
    clean them up. The script would need a change (see below).
  - WAL needs shared memory on the same machine. That normally works on a
    Railway volume, but it was not tested there.
  - WAL is stored inside the database file. Turning it off again needs a deploy
    and a moment with no other connections.
- **Revisit WAL** if backups start running while users are active (for example
  a scheduled backup job), if another process reads the live database, or if
  the database grows to where a backup takes seconds.

## Why 1 second

- A write blocked by the backup waits about 20–100 ms for today's size, and
  about 40 ms even at 25× the size. One second leaves a wide safety margin.
- A long wait freezes the whole app, so a short limit is better than 5 s. If
  something holds the lock longer, one write fails with `database is locked`
  after 1 s, instead of every user hanging for 5 s.
- Setting the value explicitly documents the choice. Otherwise it is hidden in
  a Python default.

## Resulting change

Approved and made: `LOCK_WAIT_SECONDS = 1.0` in `src/database_setup.py`,
passed as `timeout=` to `sqlite3.connect`. No schema change and no migration;
the journal mode is unchanged. A test in `tests/test_database_setup.py` checks
both values. Current behavior is stated in
[deployment: storage and process limits](../deployment.md#storage-and-process-limits).

This does not fix an observed problem. Today the only other connection is a
~20 ms deploy backup, so no one would notice either limit. It makes a hidden
Python default an explicit choice and shortens the worst case if something
ever holds the lock for long (a stuck script, or a tool opened on the live
database).

If WAL is enabled later, also make the deploy backup switch its copy to a
standalone file (`PRAGMA journal_mode=DELETE` on the copy before the checks).
That was tested locally and leaves one clean file.

## Not covered

- A write that fails with `database is locked` shows whatever generic error the
  calling page shows. How the UI handles that was not reviewed.
- Nothing was measured on Railway.
