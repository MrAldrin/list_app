# Versioned database migrations

Lifecycle: temporary

Goal: database changes run once, in order, all-or-nothing, with a backup
before any change. This is the foundation for the item-ID fix in the
[backlog](backlog.md#next).

Status: steps 1–4 implemented and tested locally; not deployed.

## Decisions

- **Own small runner, no library.** Alembic needs SQLAlchemy, a stack change
  against [`ARCHITECTURE.md`](../ARCHITECTURE.md).
- **Version number:** stored in SQLite's `PRAGMA user_version`. At startup, the
  app runs only migrations above the stored number.
- **Baseline:** today's checks in `init_database()`
  (`src/database_setup.py`) become **migration 1**. It must work on both fresh
  and legacy databases; both end at version 1.
- **On failure:** roll back and refuse to start. The error goes to the logs.
- **Integrity checks before commit:** `integrity_check` and
  `foreign_key_check`. Either failing rolls back.
- **Backups (three copies in total):**
  - **Two on this machine.** Take one before every push, following the
    [deployment checklist](../docs/deployment.md#deployment-checklist). Keep
    the newest two and delete older ones.
  - **One on the Railway volume.** At startup, only when a migration is
    pending, the app writes a verified backup-API copy to the volume before
    migrating. Each new copy replaces the previous one. If the backup fails,
    do not migrate and refuse to start. This copy guards against a bad
    migration, not against losing the volume.
- **Where the volume backup runs:** app startup, not Railway's pre-deploy
  command. Pre-deploy does not have the volume mounted.

## Technical notes

- Python's `sqlite3` does not open a transaction before `CREATE`/`ALTER`
  statements by default. The runner must start the transaction explicitly
  (`BEGIN`), or rollback will not undo schema changes.
- Table rebuilds need `PRAGMA foreign_keys = OFF`, which SQLite ignores inside
  a transaction. Turn it off before `BEGIN`, run `foreign_key_check` before
  commit, then turn it back on. The current code already does this at the
  level of the whole function.
- The volume backup path is an environment setting next to `DB_PATH`, with a
  default next to the database file. The backup reuses the procedure in the
  [deployment guide](../docs/deployment.md#sqlite-consistent-backups), but
  replaces the old file only after the new copy is verified.
- Rebuild a table in SQLite's documented order: create the new table, copy,
  drop the old one, rename the new one. Renaming the old table first repoints
  other tables' foreign keys at it.
- Tests use temporary databases, never production data.

## Steps

1. **Runner:** read `user_version`, take the backup if needed, run pending
   migrations in one transaction, check integrity, set the new version,
   commit. Tests: fresh database, already up to date, failure rolls back and
   keeps the version, integrity failure rolls back.
2. **Baseline:** move current `init_database()` schema work into migration 1.
   Tests: fresh, legacy, missing-foreign-key, already-migrated and
   invalid-data databases all behave as today.
3. **Volume backup:** copy before migrating, only when a migration is pending.
   Tests: no copy when up to date; copy made and verified before migrating;
   backup failure stops startup; the new copy replaces the old one.
4. **Docs:** update the [deployment guide](../docs/deployment.md) (keep two
   local copies, where the volume copy lives, how to restore from it) and the
   [backup plan](backup-options.md). Remove the backlog item.
5. **Production:** see the runbook below.

## Deploy runbook (step 5)

For the agent helping the owner deploy. Follow the
[deployment checklist](../docs/deployment.md#deployment-checklist); this adds
the migration-specific steps. Report the result of each step before the next.

**What ships:** bookmark `deploy-backup` and everything below it that is not
on `main` yet: the migrations and the
[deploy backup script](../docs/deployment.md#backup-before-deploying). Check
with `jj log -r 'main..deploy-backup'`.

1. **Backup:** `uv run python scripts/deploy_backup.py --backup-only`. It
   checks the result and keeps the two newest local copies.
2. **Rehearse on a copy:** copy that backup to the job's temp folder and start
   the new code against it twice, with a dummy `APP_PASSWORD` and
   `PYTHON_DOTENV_DISABLED=1`. Expect: first start prints
   `Database migrated from version 0 to 1`, second prints nothing;
   `list-pre-migration.db` matches the original; existing values unchanged
   (new columns are fine); integrity and foreign-key checks clean. Delete the
   copies afterwards.
3. **Checks:** `uv run pytest -q`, `uv run ruff format --check .`,
   `uv run ruff check .` on the bookmark.
4. **Push:** the owner runs
   `uv run python scripts/deploy_backup.py --rev deploy-backup`. It refuses
   outside the deploy window, takes one more backup, shows what goes live and
   pushes `main` only after the owner types `y`. Railway deploys from `main`.
5. **After deploy:**
   - Logs show `Database migrated from version 0 to 1` and no errors.
   - `/data/list-pre-migration.db` exists (for example `ls -l /data` over
     `railway ssh`).
   - The deployment checklist's after-deploy checks pass; the owner does the
     browser and device checks.
6. **If it fails to start:** do not retry blindly. Read the log. Roll back by
   moving `main` back to the previous revision (the old code ignores the
   version number); restore a backup only if data looks wrong, following
   [restoration](../docs/deployment.md#restoration-and-rollback).
7. **Finish:** tick step 5 below; remove the backlog item; delete this plan in
   its own final jj change (it is `temporary`) after fixing links to it.

## Progress

- [x] 1. Runner
- [x] 2. Baseline migration 1
- [x] 3. Volume backup at startup
- [x] 4. Docs
- [x] 5. Production deploy and check
