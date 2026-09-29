# Backup plan for the Railway SQLite app

Lifecycle: tracked

Status: manual, verified local copies exist; no recurring backup, alerting, encrypted off-service storage or hosted restore drill is set up. Interim goal: weekly Railway snapshots plus occasional manual SQLite backups. Commands are in the [deployment guide](../docs/deployment.md#sqlite-consistent-backups); option comparison, Railway CLI findings and evidence are in [background](../docs/background/backup-research.md).

## Recommended sequence (requires owner approval before production changes)

1. **Pick an owner and recovery target.** Agree how many hours of changes can
   be lost (weekly backups can lose up to a week) and who receives failure
   alerts. For later automated off-service copies, choose encrypted storage
   controlled separately from this Railway volume, with access limited to the
   owner/restore operators. Decide its frequency and retention separately.
2. **Start with a manual, verified backup-API copy.** Confirm production path,
   disk headroom and permissions; run the guide's procedure on the service via
   SSH at a quiet time, with a unique filename. Download only the finished
   backup; verify checksum, `integrity_check`, `foreign_key_check`, and
   representative data in a protected location. Copy encrypted off-service.
   Do not log secrets, rows or database contents. Keep one extra verified copy
   immediately before schema-changing deploys.
3. **Add layered scheduling.** Start with Railway **weekly** volume snapshots
   in the service Backups tab for fast whole-volume recovery. Keep occasional
   verified SQLite backups on a private local machine. If backup needs grow,
   separately automate the SQLite backup-API + off-service
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

## Weekly Railway schedule and future home backup server

The CLI (5.62.1) has no `railway volume backup` scheduling command, but
`railway api` exposes the `volumeInstanceBackupScheduleUpdate` mutation. On
2026-09-25, a read-only query identified the production `/data` volume instance
and confirmed it had **no** schedule or snapshots. The CLI mutation to enable
`WEEKLY` returned `Not Authorized`; a follow-up query still returned an empty
schedule. The reason for rejection is not known; do not infer that Free accounts
cannot use the Backups tab. No schedule was created.

**Manual next step:** In Railway's production `list_app` service, open
**Backups** and select **Weekly** for the `/data` volume. Check it is saved and
listed; after its first due date, check a snapshot appears. If the control is
absent or disabled, check the account plan and permissions before changing the
strategy. Railway's documented weekly snapshots expire after 27 days and are
not a verified SQLite-consistent off-service copy. Continue occasional manual
local backups until a separate schedule is designed.

**Later option, not configured:** Reuse an old laptop with Linux as an always-on
backup receiver, separate from Railway. Decide how to produce verified SQLite
backup-API files, move them without exposing a public file share, encrypt and
retain them, monitor missed jobs and disk/power/network failure, and drill a
restore. A powered-off machine cannot meet a weekly schedule. This is not
needed to start with Railway snapshots; do not set up remote access or backup
credentials without a separate design and approval.

## Progress tracking

- [x] Review current architecture and deployment guide
- [x] Compare backup/transfer methods and check current Railway CLI/docs
- [x] Test SQLite backup API locally on disposable WAL-mode data
- [x] Make and verify one production-to-local copy; remove only the temporary
  Railway copy
- [ ] Enable and verify Weekly in Railway's dashboard (CLI mutation was denied)
- [ ] Choose owner, recovery target, storage, alerts and retention
- [ ] Design/test automated off-service transfer and hosted restore
  (tracked in the [backlog](backlog.md))
