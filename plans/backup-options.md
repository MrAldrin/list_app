# Backup plan for the Railway SQLite app

Lifecycle: tracked

**Status:** Each deploy includes a backup ([deployment guide](../docs/deployment.md#backup-before-deploying)). The app has no recurring backup, alerting, encrypted off-service storage, or hosted restore drill.

**Blocker:** Railway volume snapshots are not available on the owner's current Railway plan. Until the plan changes, the only option is a local copy pulled from Railway by a scheduled job on an owner-controlled machine. The job is deferred to [Ideas](backlog.md#ideas). Until then, backups happen on each deploy. The app also keeps one [pre-migration copy](../docs/deployment.md#schema-migrations) on the volume.

Commands are in the [deployment guide](../docs/deployment.md#sqlite-consistent-backups); option comparison, Railway CLI findings and evidence are in [background](../docs/background/backup-research.md).

## Recommended sequence (requires owner approval before production changes)

1. **Pick an owner and recovery target.** Agree how many hours of changes can
   be lost. Weekly backups, for example, can lose up to a week of changes.
   Choose who receives failure alerts. For later automated off-service copies,
   choose encrypted storage controlled separately from this Railway volume.
   Limit access to the owner or restore operators. Decide the copy frequency
   and retention separately.
2. **Start with a manual, verified backup-API copy.** Confirm the production
   path, disk headroom, and permissions. Run the guide's procedure on the
   service via SSH at a quiet time. Use a unique filename. Download only the
   finished backup. In a protected location, verify the checksum,
   `integrity_check`, `foreign_key_check`, and representative data. Copy the
   backup to encrypted off-service storage. Do not log secrets, rows, or
   database contents. Keep one extra verified copy immediately before
   schema-changing deploys.
3. **Schedule a pull job.** Railway snapshots are blocked on the current plan
   (see [below](#scheduled-local-copy-railway-snapshots-blocked)). Run a
   scheduled job on an owner-controlled machine to make a SQLite backup-API
   copy on Railway, download and verify it, and apply retention.
   Alert on missed or failed backups. Do not assume that a separate Railway
   cron *service* can see the app's volume. Railway's docs only guarantee the
   volume mount to the attached service, not access from a separate cron
   service. Assess an authorized external scheduler or another proven
   arrangement before implementation. Never store backup credentials in
   source control.
4. **Drill restores before trusting the schedule.** Restore a transferred file
   to an isolated/disposable app with compatible code. Check integrity,
   representative rooms/items, and startup. Test hosted recovery with the app
   stopped and no auto-redeploys. Railway's snapshot restore stages a new
   volume for deployment. A file restore follows the deployment guide's
   sidecar/permissions procedure. **Never trial a Railway snapshot restore
   against the only production volume**: it is limited to the same
   project/environment. Create a separate disposable environment/volume and
   its own snapshot for a safe drill. The production snapshot cannot be
   restored there. Record duration, backup age, and any data loss.
5. Monitor the last *successful and restorable* off-service backup, transfer
   failures, free volume space, and retention. Review backup access and repeat
   the drill periodically. None of these checks are complete yet.

## Scheduled local copy (Railway snapshots blocked)

**Blocker:** Railway volume snapshots are not available on the owner's current
Railway plan. The 2026-09-25 CLI attempt to enable a weekly schedule returned
`Not Authorized`; details are in [background](../docs/background/backup-research.md).
Revisit only if the Railway plan is upgraded.

**Chosen direction, not configured:** a scheduled job that pulls a verified
SQLite copy from Railway to one of:

- **This machine**, with a reminder or scheduler. Simple, but misses runs when
  the machine is off.
- **An always-on home machine** (for example an old Linux laptop). Reliable
  schedule, but needs secure credentials, disk encryption, power/network
  monitoring and alerts.

Both use the backup-API procedure in the
[deployment guide](../docs/deployment.md#sqlite-consistent-backups). Design and
approve how the job authenticates to Railway before storing any credentials.

## Progress tracking

- [x] Review current architecture and deployment guide
- [x] Compare backup/transfer methods and check current Railway CLI/docs
- [x] Test SQLite backup API locally on disposable WAL-mode data
- [x] Make and verify one production-to-local copy; remove only the temporary
  Railway copy
- [ ] ~~Enable Weekly Railway snapshots~~ blocked: not available on current Railway plan
- [ ] Choose target machine (this machine or always-on home machine) and schedule the pull job
- [ ] Choose owner, recovery target, storage, alerts and retention
- [ ] Design/test automated off-service transfer and hosted restore
  (tracked in the [backlog](backlog.md))
