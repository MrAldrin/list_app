# Deploy backup script

Lifecycle: temporary

Make "back up production before pushing `main`" one command, so a push cannot
happen without a fresh, verified local copy. Replaces the manual backup step in
the [deployment checklist](../docs/deployment.md#deployment-checklist).

## Decisions

- **Manual trigger, no schedule.** jj has no hooks and `jj git push` does not
  run git hooks, so the owner runs a script instead of pushing by hand. A
  scheduled backup job is deferred to the [backlog](backlog.md#ideas).
- **Order is fixed:** back up → verify → show what ships → ask → push. Any
  failure stops the script before the push.
- **Push needs a typed `y`** after the change list is shown. The script is the
  owner's action; an agent never runs it without explicit approval.
- **Deploy window:** the script refuses to push outside 20:00–08:00
  Europe/Oslo. `--backup-only` takes a backup at any time and never pushes.
- **Railway procedure** follows the proven manual one in
  [backup research](../docs/background/backup-research.md#can-we-use-the-railway-cli-for-direct-queries-or-backups):
  a backup-API copy to a unique file on `/data` over `railway ssh`, checked
  there, downloaded with `railway volume files download`, then deleted from the
  volume.
- **Local copies** go to `~/.local/share/list_app/backups/` (folder `0700`,
  files `0600`). The script keeps the two newest and asks before deleting
  older ones. It never overwrites a file.
- **Uses the linked Railway project.** The volume is the one mounted at
  `/data`. The script shows project and environment and stops unless the
  environment is `production`.
- Python with the standard library only, run with `uv run`. Railway and jj are
  called as subprocesses, so tests replace them with fakes and never touch
  production.

## Steps

1. **Plan and backlog:** this file; add the backlog item; move the scheduled
   job to Ideas.
2. **Script and tests:** `scripts/deploy_backup.py` with `--backup-only` and
   `--rev <revision>` (required unless `--backup-only`; no guessing what ships).
   Tests cover the deploy window, retention, local
   verification, the remote script's output parsing, and the stop-on-failure
   order with a fake command runner.
3. **Docs:** deployment checklist and backup section point to the script;
   update the backup plan status. Remove the backlog item.
4. **First real run (owner):** `--backup-only` against production, outside a
   deploy if preferred. Check that a verified copy lands locally and the temp
   file is gone from the volume.

## Progress

- [x] 1. Plan and backlog
- [x] 2. Script and tests
- [ ] 3. Docs
- [ ] 4. First real run (owner)
