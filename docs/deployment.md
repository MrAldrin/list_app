# Deployment and recovery

ListR uses one NiceGUI application instance and one SQLite database. Production
runs on Railway with a persistent volume (storage that survives deployments).
For local setup, see the [README](../README.md).

## Configuration

| Variable | Purpose |
| --- | --- |
| `APP_PASSWORD` | Required, nonblank admin password; also used when first creating the default `Home` room. |
| `NICEGUI_STORAGE_SECRET` | Required private signing key for NiceGUI session storage. Use a separate random value and keep it stable across restarts. |
| `DB_PATH` | Database file path. Production: `/data/list.db` on the `/data` persistent volume. Default: `list.db` in the repository root. |
| `PORT` | Listening port; defaults to `8080`. The `--port` argument takes precedence. |
| `APP_RELOAD` | Automatic restart on code changes. Defaults to off; only `true` (case-insensitive, surrounding whitespace ignored) enables it. |

Generate separate secrets using the command in the README. The app explicitly
rejects missing/blank `APP_PASSWORD` before opening the database. There is no
password-free development mode. `NICEGUI_STORAGE_SECRET` is read directly at
startup: a missing value fails startup; do not assume blank values are validated.

`APP_PASSWORD` protects `/admin`. Changing it does **not** change existing room
passwords. Use the room password-reset controls for those; resets revoke existing
room access tokens. Keep the storage secret unchanged during ordinary deploys;
rotating it can invalidate NiceGUI sessions.

- Railway uses service environment variables, not the untracked local `.env`.
- The production app password is randomly generated and stored in Bitwarden.
- Keep all secrets, database files, and backups out of version control and public logs.
- Local `.env` values are loaded by `python-dotenv`; existing environment values
  take precedence.

## Build and startup

Use Python 3.13 or newer. With uv available:

```bash
uv sync --locked
uv run python src/main.py
```

The repository's `Procfile` declares `web: python src/main.py`; this assumes the
build has installed dependencies into the Python environment used at runtime.
Use Railway's supplied `PORT` and route traffic to that port. The application
binds to `0.0.0.0` (all interfaces).

Use `APP_RELOAD=true` only for local development. On Railway, no new variable is
needed: leave it unset or set it to `false`. With reload off, code updates take
effect after an explicit restart or deployment, not through a file watcher.

**Known limitations, tracked in the [backlog](../plans/backlog.md):**

- Startup performs schema changes automatically. Versioned, transaction-safe
  migrations and recurring backup automation are still pending.

## Persistent storage and process limits

- Mount the Railway volume at `/data` and set `DB_PATH=/data/list.db`.
  The parent directory must exist and be writable by the application.
- Keep one application service/instance using this database: no horizontal
  replicas or extra application workers. The optional development reload supervisor
  is not a supported multi-worker deployment strategy.
- Do not place the production database on the temporary deployment filesystem.
  A wrong or missing `DB_PATH` can create a new, empty database instead of opening
  the existing one. Check the path before starting or restoring.

## HTTPS and reverse proxy

Use Railway's HTTPS endpoint (or a properly configured HTTPS reverse proxy).
The proxy must support WebSocket upgrades for NiceGUI's live updates and preserve
the public host and original HTTPS scheme in the app's normalized request data.

Cookie writes and Socket.IO handshakes enforce same-origin checks. A mismatched
host or an app that sees public HTTPS requests as HTTP can break remembered
access or live updates. Configure forwarded-header trust for the actual proxy;
do not blindly trust headers from arbitrary internet clients or expose a bypass
around the trusted proxy. If proxy settings need changing, validate them against
the installed NiceGUI/Uvicorn version rather than assuming an app CLI flag exists.

HTTPS remembered-room cookies are Secure/HttpOnly/SameSite=Lax. Local HTTP uses
the localStorage fallback, so local testing alone does not verify production
cookie behavior. See the [device checklist](home-screen-installation.md).

## Public share-link rollout

Secure public links require an automatic token backfill and restrict old list
URLs. Back up before deploying and follow the [sharing rollout checks](public-sharing.md#rollout-and-verification).
Production and real-device verification remain pending.

## Deployment checklist

Before deploying:

- [ ] Confirm both secrets, absolute `DB_PATH`, volume mount, port, and one instance.
- [ ] Record the deployed code revision and make a SQLite-consistent backup below.
- [ ] For schema changes, first start the candidate version against a **separate
  copy** of the backup in an isolated environment. Never use production's path or
  expose the copied data publicly.

After deploying:

- [ ] Review startup logs for errors. Startup enables foreign keys and checks for
  foreign-key violations after its schema setup; also run the read-only checks below.
- [ ] Confirm existing rooms, lists, and representative item fields/counts remain.
- [ ] Test admin login, room login, and add/edit/toggle/delete with disposable data.
  Check live updates in two browsers and confirm public-list behavior.
- [ ] Restart/redeploy and confirm a disposable saved item survives. Verify remembered
  room access and that a room password reset revokes prior access.
- [ ] Verify HTTPS cookies and home-screen installation on real devices using the
  linked checklist. Automated tests do not replace these checks.

These are instructions, not a claim that all production checks have been run.

## SQLite-consistent backups

A raw copy of a live SQLite file can be inconsistent or omit journal/WAL data.
Use SQLite's backup API for live backups. Run this with Python on the host that
has the volume mounted; replace the example destination with a **new** filename:

```bash
DB_PATH=/data/list.db BACKUP_PATH=/private/backups/list-before-deploy.db python - <<'PY'
import os
import sqlite3
from pathlib import Path

source = Path(os.environ['DB_PATH']).resolve(strict=True)
target = Path(os.environ['BACKUP_PATH'])
target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
target.touch(mode=0o600, exist_ok=False)  # Refuse to overwrite a backup.
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
        assert dst.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert dst.execute('PRAGMA foreign_key_check').fetchall() == []
print('Backup verified:', target)
PY
```

Check the command succeeded before using the backup. Restrict access to the backup
directory, including pre-existing directories; backups contain private list data
and authentication records. Transfer a protected copy off the Railway service/volume.
A backup only on the same volume does not protect against losing that volume.

**Interim goal, not yet configured:** weekly Railway volume snapshots plus
occasional manual, SQLite-consistent local copies and a backup before each
schema-changing deploy. The [one-off production-to-local test](../plans/backup-options.md#evidence-and-limits)
on 2026-09-24 does not establish a recurring policy or a tested restore.
Railway's schedule is still **absent**; see the [manual dashboard step and future
options](../plans/backup-options.md#weekly-railway-schedule-and-future-home-backup-server).
Choose an owner, failure notification, off-service storage policy and restore
drill before treating longer-term recovery as operational. The earlier one-time
repair backup is not a recurring backup policy either.

## Read-only database checks

Run on the mounted volume, or against a backup by changing `DB_PATH`:

```bash
DB_PATH=/data/list.db python - <<'PY'
import os
import sqlite3
from pathlib import Path

path = Path(os.environ['DB_PATH']).resolve(strict=True)
with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
    integrity = db.execute('PRAGMA integrity_check').fetchall()
    foreign_keys = db.execute('PRAGMA foreign_key_check').fetchall()
    print('Integrity:', integrity)
    print('Foreign-key violations:', foreign_keys)
    assert integrity == [('ok',)]
    assert foreign_keys == []
PY
```

Expected: integrity `ok`, no foreign-key violations. These checks do not prove
that all business data survived; compare representative records/counts as well.

## Restoration and rollback

1. Stop the application and prevent automatic restarts or deploys. Confirm no
   process is using the database. Arrange maintenance access to the mounted volume.
2. Select a verified backup and compatible code revision. Restore to a separate
   file first and run the read-only checks above. Restoring loses changes made
   since that backup; confirm this trade-off before proceeding.
3. Preserve the failed database and any `-wal`, `-shm`, or `-journal` sidecar files
   together in a restricted recovery directory with the app stopped. Do not discard
   them or combine old sidecars with the restored database.
4. Copy the verified backup to the configured `DB_PATH`, ensuring the original
   files/sidecars have been moved aside. Set ownership/permissions so only the
   intended service and operators can access it and the app can write it.
5. Start the compatible code, inspect logs, rerun integrity/foreign-key checks,
   and repeat the smoke and persistence checks. Keep recovery files until success
   is confirmed.

**Rolling back code does not undo a database migration.** An older version may
not understand the newer schema. Restore a matching backup when necessary rather
than repeatedly starting incompatible versions against the only data copy.

Test this procedure on a disposable database before relying on it. A real hosted
restore drill, recurring backup setup, and device/restart verification remain
separate backlog work.
