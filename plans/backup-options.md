# Backup options for the Railway SQLite app

Research reviewed: 2026-09-24. A **one-off local copy** was verified on
2026-09-24, but no recurring backup schedule, alerting, encrypted off-service
storage, or hosted restore drill has been set up. The operational
backup/check/restore commands and proposed policy live in the
[deployment guide](../docs/deployment.md#sqlite-consistent-backups).

## What we have today

ListR runs one NiceGUI process with SQLite at `DB_PATH=/data/list.db` on one
Railway volume mounted at `/data` (see the [architecture](../ARCHITECTURE.md)).
The repository has no recurring backup job; Railway backup settings have not
been inspected. Startup may change the schema. A local
`.env` and `list.db` are **not** the hosted database. Read-only `railway status`
on 2026-09-24 showed a linked production service with a `/data` volume
(51 MB used of 500 MB), and the CLI was logged in (version 5.57.2). This is
volume usage, **not** a measurement of `list.db`; it does not establish the
volume backup schedule or database integrity. A one-off production backup was
subsequently made and verified as described below; no production records were
printed or exported to this repository.

## Comparison

| Option | Usefulness | Limitations here |
| --- | --- | --- |
| SQLite online backup API (`sqlite3.Connection.backup()` in Python, or SQLite CLI `.backup`) | Makes a consistent database snapshot while the app can keep writing; one database file to verify and transfer. The deployment guide already contains a Python example. | Must run where `/data` is mounted, have free space, then copy securely off Railway. Scheduling, failure alerts, retention, and restore testing are ours to arrange. |
| Railway volume backups | Built-in scheduled daily/weekly/monthly and manual volume snapshots; convenient whole-volume recovery. Restoration stages a replacement volume and redeploy, retaining the previous volume unmounted. | Same Railway project/environment only; wiping the volume deletes its backups. Railway's docs do **not** promise a SQLite transaction-consistent backup of a live database with journal/WAL sidecars. Do not treat this as the only verified database backup. Manual backups have a 50%-of-volume-capacity size limit; check actual size and plan. |
| Stop app, copy database **and** sidecars (`-wal`, `-shm`, `-journal` when present) | Simple emergency fallback if the app is definitively stopped and the set is preserved together. | Downtime and easy to miss sidecars; raw copy or CLI download of only `list.db` while live can be incomplete/inconsistent. Not a recurring live-backup method. |
| SQLite `VACUUM INTO` | Another SQLite-supported consistent live snapshot, compacted. | Requires free space and an additional path for generation/transfer. No advantage for this small app over the existing tested backup-API procedure; don't add a second mechanism without a reason. |

Railway's documented retention for scheduled volume backups is **6 days**
(daily), **27 days** (weekly), and **89 days** (monthly); these are fixed
schedule lifetimes, not our proposed seven-daily/four-weekly off-service
retention. Volume snapshots are incremental and billed for incremental data.
Neither snapshot scheduling nor off-service storage is verified as configured.

## Can we use the Railway CLI for direct queries or backups?

**Yes, from the service container; not via a local `railway run`.** `railway
ssh` can run a Python command inside the deployed service, where `/data` is
mounted. After checking the service, environment, path, free space and access,
an operator could run the deployment guide's Python backup-API procedure
there with `DB_PATH=/data/list.db` and a **fresh** `BACKUP_PATH` on `/data`.
SQLite read-only SQL (e.g. `PRAGMA integrity_check` and
`PRAGMA foreign_key_check`) can be run there too, using the deployment guide's
checks. Python is available in this app; don't assume the `sqlite3` CLI binary
is installed in the deployed image. **Do not run queries or download production
data merely to check whether the CLI works.** The service was sleeping when
metadata was first checked. SSH access and a one-off backup were subsequently
tested after waking the service with a normal page request; this is not a
recurring job.

After creating and verifying a snapshot file, use
`railway volume files --volume <volume-id> download /<unique-backup>.db
<private-path-outside-repo>` or Railway SSH/SFTP/SCP to transfer that **backup
file**, not the live `list.db`. The volume-files CLI supports noninteractive
download and refuses to overwrite an existing local path by default. Confirm
that volume-file paths are relative to the volume root; restrict the local
destination and encrypt before sending to independent off-service storage.
Verify checksum and SQLite integrity on the received copy. Do not leave
unbounded copies on the volume. Test that the chosen transfer works with this
service before automating it.

`railway run` injects Railway environment variables into a **local** process;
it does not mount the remote `/data`. Running SQLite against its `DB_PATH` on
this machine will therefore not read production and may create an unintended
local database. `railway connect` targets managed database shells, not this
SQLite file. The installed CLI's `railway volume` commands expose file access,
not a SQLite-aware backup operation; schedule Railway's native snapshots in the
service **Backups** tab rather than assuming the CLI creates them.

## Recommended sequence (requires owner approval before production changes)

1. **Pick an owner and recovery target.** Agree how many hours of changes can
   be lost (daily backups can lose up to a day) and who receives failure alerts.
   Choose encrypted storage controlled separately from this Railway volume,
   access limited to the owner/restore operators. Decide whether seven daily
   and four weekly off-service copies in the deployment guide meet the target.
2. **Start with a manual, verified backup-API copy.** Confirm production path,
   disk headroom and permissions; run the guide's procedure on the service via
   SSH at a quiet time, with a unique filename. Download only the finished
   backup; verify checksum, `integrity_check`, `foreign_key_check`, and
   representative data in a protected location. Copy encrypted off-service.
   Do not log secrets, rows or database contents. Keep one extra verified copy
   immediately before schema-changing deploys.
3. **Add layered scheduling.** Enable Railway volume daily/weekly snapshots in
   the service Backups tab for fast whole-volume recovery (optionally monthly,
   subject to cost). Separately automate the SQLite backup-API + off-service
   transfer, retention and alert on missed/failed backups. A separate Railway
   cron *service* should not be assumed to see the app's volume: Railway's
   docs only guarantee its mount to the attached service, not access from a
   separate cron service. Assess an authorized external scheduler or
   another proven arrangement before implementation. Never store backup
   credentials in source control.
4. **Drill restores before trusting the schedule.** Restore a transferred file
   to an isolated/disposable app with compatible code; check integrity,
   representative rooms/items and startup. Test hosted recovery with the app
   stopped and no auto-redeploys; Railway's snapshot restore stages a new
   volume for deployment, whereas a file restore follows the deployment
   guide's sidecar/permissions procedure. **Never trial a Railway snapshot
   restore against the only production volume**: it is limited to the same
   project/environment. Create a separate disposable environment/volume and
   its own snapshot for a safe drill; production's snapshot cannot be restored
   there. Record duration, backup age and any data loss.
5. Monitor last *successful and restorable* off-service backup, transfer
   failures, free volume space and retention. Review backup access and repeat
   the drill periodically. None of these checks are complete yet.

## Evidence and limits

- Local disposable SQLite test: `sqlite3.Connection.backup()` produced an
  integrity-clean snapshot of a live WAL-mode database; a later source write
  did not appear in the copy. This demonstrates API behavior locally only.
- **One-off production-to-local test, 2026-09-24:** After confirming the linked
  production service, `/data/list.db`, and free volume space, a Python SQLite
  backup-API snapshot was written to a unique temporary file on the volume.
  Railway-side `integrity_check` and `foreign_key_check` passed. The backup was
  downloaded via `railway volume files` to
  `~/.local/share/list_app/backups/list-manual-20260924T213006Z-6e26b172.db`
  (86,016 bytes). On the local copy, SHA-256 matched the Railway snapshot;
  integrity, foreign keys, and expected tables passed; file permissions were
  `0600` inside a `0700` directory. The verified temporary file was removed
  from Railway; the **local copy remains**. It is not encrypted by this
  procedure; protect the machine and do not commit or share the file.
  **No full restore, routine backup, failure alert, or long-term retention was
  tested.** The source database was not overwritten or restored.
- [SQLite online backup API](https://www.sqlite.org/backup.html)
- [Railway volume backups: schedules, restore, limits and caveats](https://docs.railway.com/volumes/backups)
- [Railway volumes: mount and service limitations](https://docs.railway.com/volumes/reference)
- [Railway CLI volume file transfers](https://docs.railway.com/cli/volume)
- [Railway SSH and SFTP/SCP](https://docs.railway.com/cli/ssh)
- [Railway run (local execution)](https://docs.railway.com/cli/run)

## Progress tracking

- [x] Review current architecture and deployment guide
- [x] Compare backup/transfer methods and check current Railway CLI/docs
- [x] Test SQLite backup API locally on disposable WAL-mode data
- [x] Make and verify one production-to-local copy; remove only the temporary
  Railway copy
- [ ] Choose owner, recovery target, storage, alerts and retention
- [ ] Configure/test production schedules, automated off-service transfer and hosted restore
  (tracked in the [backlog](backlog.md))
