# Versioned database migrations

Lifecycle: temporary

Goal: database changes run once, in order, all-or-nothing, with a backup
before any change. This is the foundation for the item-ID fix in the
[backlog](backlog.md#next).

Status: approved design, not implemented.

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
5. **Production:** follow the deployment checklist. After deploy, check the
   logs show version 1 and that the volume copy exists. Needs approval to push
   `main`.

## Progress

- [x] 1. Runner
- [x] 2. Baseline migration 1
- [x] 3. Volume backup at startup
- [ ] 4. Docs
- [ ] 5. Production deploy and check
