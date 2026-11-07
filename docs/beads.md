# Local tasks in Beads

Beads holds task status. [Plans](../plans/backlog.md) hold supporting scope,
decisions and evidence. Native Ready means no recorded blocker, not approval
to start. The [scope gates](scope.md#gates) still apply.

## Use one primary store

All jj workspaces on this machine use
`/home/hsa/projects/list_app/.beads`. Do not initialize another store in a code
workspace. Do not put this project path in global shell settings.

Use an explicit store and primary directory on every command. In Fish:

```text
env BEADS_DIR=/home/hsa/projects/list_app/.beads bd -C /home/hsa/projects/list_app where
env BEADS_DIR=/home/hsa/projects/list_app/.beads bd -C /home/hsa/projects/list_app list --all --limit 0
env BEADS_DIR=/home/hsa/projects/list_app/.beads bd -C /home/hsa/projects/list_app ready --limit 0
env BEADS_DIR=/home/hsa/projects/list_app/.beads bd -C /home/hsa/projects/list_app list --status blocked --limit 0
env BEADS_DIR=/home/hsa/projects/list_app/.beads bd -C /home/hsa/projects/list_app list --status deferred --limit 0
```

Before a write, run `where` yourself and check the exact primary path. Stop if
it differs. Source labels and metadata preserve the old groups and order;
native state is separate. Do not turn a historical owner or session reference
into an active task claim.

## Claim only approved work

Use a unique actor containing the full current session ID. Claim one selected
record with `update TASK-ID --claim`, using the explicit store and flags above
and `--actor ACTOR`. Replace both placeholders. A rejected claim means stop
and inspect ownership; do not force it or start duplicate work.

Only the recorded claimant closes its work. Check the current assignee and
status first. Record the result and evidence through a protected file or stdin.
Use `update TASK-ID --if-assignee ACTOR --if-status in_progress --status closed`
with the same actor and explicit store flags. The guards reject changed
ownership or status. Do not force closure, bypass an open prerequisite, or
close imported work merely because migration is done. The shared backlog/plan
write rules in [AGENTS.md](../AGENTS.md) still apply.

## Private operation and recovery

Start migration or review processes with umask `077` and private runtime and
`TMPDIR` directories. Check owned directories are mode `700`, files are `600`,
and their ancestry has a private boundary. Native Dolt can create metadata
with broader modes despite the umask. During preparation, audit owned native
paths after each command. Correct known native-created files to `600` and
directories to `700` only inside a verified owned private root. Stop on an
unexpected owner, path, symlink or opened private boundary; do not change a
shared backup parent. Private child work also requires a verified model/tier,
loaded runtime doctor and a synthetic fresh no-tools canary before source
reads. Keep task text out of command arguments; use protected files or stdin.
Keep the local native store and runtime evidence private. Beads data sync uses
only the private target named in [AGENTS.md](../AGENTS.md).

The database lives in `.beads/embeddeddolt/`. Keep the full native store, its
configuration and private companions, and the sibling `.beads.gate.lock`.
Lock files are not task claims. Do not remove them while Beads is in use.

Native backup destination:
`/home/hsa/.local/share/beads-backups/list_app/native`.
Use the same explicit store selection for `backup sync` and `backup status`.
Automatic export, staging and backup stay disabled. For task sync, follow
"Sync with GitHub" in the shared PRIME.md. Keep code Git remotes unchanged.

An issue JSONL export is not a full backup. Recovery needs a native backup and
a new isolated, initialized destination with an explicit `BEADS_DIR` from its
first init. `backup restore --force` replaces its destination: use it only on
that new disposable store, never on the working store as a check. Compare full
records, metadata, states, claims, edges and unlimited history, events,
journal, provenance and recorded Dolt log. Do not use standalone Dolt during a
read-only review; inspect the protected preparation evidence instead.

This backup is on the same PC. It does not protect against loss of the machine
or disk. Private Beads sync follows the shared PRIME.md. No other remote
backup, service, publication or deployment is approved.
