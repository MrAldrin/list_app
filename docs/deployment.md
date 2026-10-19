# Deployment and recovery

ListR runs as one Python process (FastAPI on uvicorn, serving the Svelte frontend
and the JSON API) with one SQLite database. Production runs on
Railway with a persistent volume (storage that survives deployments).

Railway deploys automatically when GitHub `main` changes. Moving the local
`main` bookmark does nothing until it is pushed, so treat a push to `main` as a
production deployment and follow the [checklist](#deployment-checklist). For
local setup, see the [README](../README.md).

## Railway plan

Production runs on Railway's Hobby plan, so deploys are allowed at any time.
The workspace has a $10 compute usage limit: Railway stops the app if usage
reaches it. Raise the limit in the workspace's Usage page if that happens.

## Configuration

| Variable | Purpose |
| --- | --- |
| `APP_PASSWORD` | Required admin password for `/admin`. Also sets the password of the default `Home` room when it is first created. |
| `DB_PATH` | Database file. Production: `/data/list.db`. Default: `list.db` in the repository root. |
| `DB_BACKUP_PATH` | Pre-migration copy. Default: next to `DB_PATH`, e.g. `/data/list-pre-migration.db`. |
| `PORT` | Listening port, default `8080`. `--port` overrides it. |
| `APP_RELOAD` | Restart on code changes. Off unless set to `true`. Use only locally. |
| `FORWARDED_ALLOW_IPS` | Proxies whose forwarded headers are trusted. Production: `*`, so the app sees Railway's HTTPS and sets the `__Host-` cookies. The app is reachable only through Railway's proxy. |
| `REQUIRE_FRONTEND_BUILD` | Set to `true` by the Dockerfile. Startup fails if `frontend/build/` is missing. |

- The app refuses to start with a missing or blank `APP_PASSWORD`. There is no
  password-free mode. Generate the value with the command in the README.
- Changing `APP_PASSWORD` does not change room passwords. Reset those from the
  room controls; a reset logs out everyone using that room.
- Railway uses its service variables, not the local `.env`. Locally, `.env` is
  loaded by `python-dotenv`, and real environment variables win.
- The production app password is stored in Bitwarden. Keep secrets, databases
  and backups out of version control and logs.

## Build and startup

Use Python 3.13 or newer. Build the frontend first (`npm ci && npm run build`
in `frontend/`), then:

```bash
uv sync --locked
uv run python src/main.py
```

The app listens on `0.0.0.0` and Railway's `PORT`. There is no session secret
to set. Room tokens are random and stored hashed; the admin cookie is signed
with a key made from `APP_PASSWORD`.

### Production image

Railway detects and builds the root `Dockerfile`, so the repository fully
defines the build. There is no `railway.json`. It has two stages:

1. Node 24: `npm ci && npm run build` in `frontend/`, which writes
   `frontend/build/`. Only that folder is kept.
2. Python 3.13 with `uv sync --locked --no-dev`, the `src/` code and the build.
   It starts `python src/main.py`. There is no `Procfile`.

The image sets `REQUIRE_FRONTEND_BUILD=true`. If `frontend/build/` is missing,
startup fails with "Svelte build not found" instead of serving a broken app.
Without that variable (local runs) the server only logs a warning.

`frontend/build/` is not committed, so the build must run on every deploy. To
test the image locally (needs podman or docker):

```bash
podman build -t listapp-test .
podman run --rm -p 8080:8080 -e APP_PASSWORD=test-password-123 \
  -e DB_PATH=/tmp/t.db listapp-test
```

Railway variables, the volume and the start command do not change. Keep the start
command and build command empty in the Railway dashboard; the `Dockerfile`
decides both.

### Railway settings to check

Railway must not override the repository. In the service settings:

- The builder shows "Dockerfile — Automatically Detected"; do not change it.
  Leave "Config file path" empty. The build log shows the `npm ci` step.
- Build command and start command are empty.
- The volume is mounted at `/data`, `DB_PATH=/data/list.db`, one replica.
- Healthcheck path is `/healthz` (set it in the service's Deploy settings).
  It answers 200 while the database answers.
- `APP_PASSWORD` is set and `FORWARDED_ALLOW_IPS=*`.

### Schema migrations

Startup applies schema changes as numbered migrations (`src/migrations.py`).
SQLite's `PRAGMA user_version` stores the last one applied; only newer ones run.

- If a migration is pending, the app first writes a verified copy of the
  database to `DB_BACKUP_PATH`, replacing the previous copy. If that fails,
  it does not migrate or start. This runs at app startup because Railway's
  pre-deploy command has no volume mounted.
- All pending migrations run in one transaction, followed by integrity and
  foreign-key checks. Any failure rolls everything back and stops startup.
- The log shows `Database migrated from version X to Y` when anything ran.
- The app refuses a database newer than its code. Restore a matching backup
  instead of rolling back code alone.
- Add changes as a new migration at the end of the list in
  `src/database_setup.py`. Never edit a deployed one.
- Rebuild a table in SQLite's documented order: create the new table, copy,
  drop the old one, rename the new one. Renaming the old table first repoints
  other tables' foreign keys at it.

## Storage and process limits

- Mount the Railway volume at `/data` and set `DB_PATH=/data/list.db`.
- A wrong or missing `DB_PATH` silently creates a new, empty database. Check it
  before starting or restoring.
- Run exactly one app instance against the database: no replicas or extra
  workers.
- SQLite uses its default rollback journal, not WAL. A write waits at most
  1 second for another connection's lock, such as a backup, then fails with
  `database is locked`. Reasons: [WAL and lock-wait findings](background/sqlite-wal-timeout.md).

## HTTPS and proxy

Use Railway's HTTPS endpoint. The proxy must pass on the public host and the
original `https` scheme. If the app sees HTTPS requests as HTTP, or the wrong
host, remembered room access breaks, because API writes check the origin. Only
trust forwarded headers from the real proxy.

On HTTPS, remembered-room cookies are Secure, HttpOnly and SameSite=Lax. Local
HTTP uses the same cookies without `Secure`, so local testing does not prove
production cookie behavior. See the
[home-screen device checks](home-screen-installation.md).

## Deployment checklist

The app has about five users and every push takes a backup, so deploys are
light. The automated tests are the main check; see the
[risk level](../AGENTS.md#risk-level-ship-and-fix-forward). If something
breaks live, fix forward or [restore](#restoration-and-rollback).

Before deploying:

- [ ] The automated tests pass (pytest, plus the browser and Android suites
  when the change touches them).
- [ ] Push with the [deploy backup script](#backup-before-deploying), not by
  hand. It runs the checks, takes a fresh backup and shows the revision being
  replaced.
- [ ] For schema changes: the migration tests pass. The app also keeps its own
  pre-migration copy.

After deploying:

- [ ] The Railway startup log has no errors.
- [ ] The app opens and an existing list still shows its items.

Device checks: see the [risk level](../AGENTS.md#risk-level-ship-and-fix-forward).

## Backup before deploying

`scripts/deploy_backup.py` backs up production to this machine, then pushes
`main`. jj has no hooks and `jj git push` does not run git hooks, so pushing
through this script is how a push gets a fresh backup. Run it from the
repository with Railway linked to production; it stops for any other
environment:

```bash
uv run python scripts/deploy_backup.py --rev <revision>   # checks, backup, push
uv run python scripts/deploy_backup.py --rev <revision> --browser  # also browser tests
uv run python scripts/deploy_backup.py --backup-only      # backup, never push
```

1. Pushing only works if `main` is an ancestor of the revision, and the
   working copy must match the revision (no uncommitted changes).
2. It runs the checks first (format, lint, types, pytest, frontend lint,
   check and vitest; `--browser` adds the browser suite). It stops on the first
   failure, before any backup. `--skip-checks` is for emergencies only.
3. It wakes the app with a web request. A sleeping Railway app does not
   answer `railway ssh`. If ssh still reaches Railway's account service
   instead of the app, it waits and tries again a few times.
4. Over `railway ssh`, it makes a backup-API copy in the container's temp
   folder (not the volume), checks it, and streams it here as text.
5. It saves the copy to `~/.local/share/list_app/backups/` and checks the size,
   checksum and integrity. Nothing is left in the container.
6. It offers to delete local copies beyond the two newest.
7. It shows the changes that will go live and pushes only after you type `y`.

Any failure stops the script before the push. A copy that fails the local
checks is kept as `*.db.unverified` for inspection.

## SQLite-consistent backups

Copying a live SQLite file can produce a broken copy. Use SQLite's backup API
instead. The [deploy backup script](#backup-before-deploying) does this for
you. To do it by hand, run this on the host with the volume mounted, using a **new** filename:

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

- Backups contain private list data and password hashes. Keep the folder
  private.
- Move a copy off the Railway volume. A backup on the same volume is lost with
  it.
- The app's own pre-migration copy (see [schema migrations](#schema-migrations))
  lives on the volume. It protects against a bad migration, not against losing
  the volume.

Backups happen on each deploy; recurring backups are not set up. Status and
options are in the [backup plan](../plans/backup-options.md).

## Read-only database checks

Run on the mounted volume, or on a backup by changing `DB_PATH`:

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

Expected: integrity `ok` and no foreign-key violations. This checks the file's
structure, not that your data is complete; also compare a few rooms and lists.

## Restoration and rollback

1. Stop the app and block automatic restarts and deploys. Make sure nothing is
   using the database.
2. Pick a verified backup and a code revision that matches its schema. After a
   bad migration, the pre-migration copy on the volume matches the previous
   deploy. Restore
   it to a separate file first and run the read-only checks. Anything changed
   since the backup will be lost.
3. Move the current database and any `-wal`, `-shm` or `-journal` files together
   into a private recovery folder. Never mix old sidecar files with the restored
   database.
4. Copy the backup to `DB_PATH`. Make sure the app can write it and nobody else
   can read it.
5. Start the app, check the logs, rerun the database checks and the
   after-deploy checklist. Keep the recovery files until everything works.

**Rolling back code does not undo a schema change.** Older code may not
understand the newer database. Restore a matching backup instead of starting
incompatible code against your only copy.

The one-time rollback steps for the Svelte deploy are history: see the
[Svelte deploy record](background/svelte-rollback.md).
