# Narrow correction review: recovery guide P1 and archive-refresh P2

Reviewer: `86787486-dbdf-4ee8-8978-d160129c1218`, requested `claude-code/claude-haiku-5-5:max`.
Tier is parent-verified; I cannot attest it myself.

## Boundary observed

- No jj, Git, remote, or network command. No config contents read. No extraction.
- Read only `recovery-guide.md`, `archive-refresh.json` (keys and note), and `review-disposition.md`.
- No guide command was executed.
- Live state, the repaired config ID, and the final budget remeasure remain parent-owned.

## P1 — recovery guide isolation: RESOLVED

Checked in `recovery-guide.md`:

- `tar --no-same-owner -xf ... -C .../repo` is present.
- The physical guard runs as `env -C /tmp python3 -I -c ...`. It checks the sandbox path, `.jj/repo` as a real directory, the store `git_target` resolving to `.git` inside the extraction, no symlinks, and no `objects/info/alternates`. It stops on any failure.
- The guard records only the names of directories under `/home/hsa/.config/jj/repos` into the extraction directory. It does not read their contents.
- The inspection `env -C` sets the physical cwd to the extraction. It unsets `JJ_CONFIG`, `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_CONFIG_PARAMETERS` and `GIT_CONFIG_COUNT`. It redirects `HOME` and `XDG_CONFIG`, `DATA`, `STATE` and `CACHE` into the extraction. It sets `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`. It uses `--ignore-working-copy` and a pinned `--at-op`, with no `-R`.
- Only one jj example is given. The names-only comparison runs from `/tmp` under `python3 -I` and fails on any change.

Residual, non-blocking hardening: the comparison checks only directory names. It would not detect a change inside an existing per-repo config directory. The guide also does not read the live repo's `.jj/repo/config-id`. The parent's live pre-check should cover both, using hashes or readback only.

## P2 — archive-refresh label: RESOLVED

`archive-refresh.json` now has a `note` field. It says the file is the initial read-only refresh at operation `dcbea95d`. It states that this is not the `f6e9450d` native recovery receipt, and it points readers to `recovery-receipt.json` and `restore-final-receipt.json`. The `frozen_op` value is unchanged, and the note removes the misleading label.

## Disposition

`review-disposition.md` matches the corrections. It says no guide command was executed and that live state and the repaired ID are the parent's responsibility. It also says the budget remeasure is still pending.

## Conditional local forget: PASS, after parent live checks

The action is exactly:

```sh
jj bookmark forget exact:reminders-s2
```

Do not add `--include-remotes`. Do not run it before the following are recorded:

1. Live `reminders-s2` points to `e50da7ce0a5456159f8206513c820e7180abbb8e` (change `wlwznqly`).
2. The current op is recorded before the action.
3. `main`, `integration`, `groups`, and the old origin refs are unchanged from the report's snapshot.
4. The live repo's `.jj/repo/config-id` is recorded (hash or readback) and unchanged.
5. The final Lead coordination is complete.

Restore, if needed, is `jj bookmark set reminders-s2 -r e50da7ce0a5456159f8206513c820e7180abbb8e`. Record the op ID after the action.

This is a correction review, not new cleanup permission. Sets A and B, remote-name deletions, the cache-only forget, and `integration@origin` changes remain unapproved.

## Blockers

None for the guide or the archive-refresh label. The only gating items are the parent's live pre-checks and final Lead coordination, and the pending budget remeasure.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Only the named files were read; no jj, Git, remote, or config-content access; no guide command executed; A/B/remotes stay unapproved."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "recovery-guide.md has tar --no-same-owner, env -C python3 -I physical guard, names-only config capture, XDG redirection, single jj example, names-only after-check; archive-refresh.json has note distinguishing dcbea95d from f6e9450d."
    }
  ],
  "changedFiles": [
    "/home/hsa/.pi/agent/sessions/--home-hsa-projects-list_app-jj-cleanup--/subagent-artifacts/outputs/86787486-dbdf-4ee8-8978-d160129c1218/jj-cleanup-escalated-independent-review.fcbe2181.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "read-only file reads of recovery-guide.md, archive-refresh.json keys/note, review-disposition.md",
      "result": "passed",
      "summary": "Corrections present; no jj/Git executed"
    },
    {
      "command": "recovery-guide.md commands",
      "result": "not-run",
      "summary": "Not executed by design"
    }
  ],
  "validationOutput": [
    "archive-refresh.json note: initial refresh at dcbea95d, not f6e9450d native receipt",
    "guide: tar --no-same-owner present; env -C /tmp python3 -I guard present; XDG_* redirected; names-only before/after"
  ],
  "residualRisks": [
    "Names-only comparison does not detect content changes in existing per-repo config directories",
    "Guide does not check live .jj/repo/config-id; parent pre-check must do it",
    "Live op, repaired ID, and final budget remeasure remain parent-owned"
  ],
  "noStagedFiles": true,
  "diffSummary": "New review artifact only; no repository files changed.",
  "reviewFindings": [
    "P1 resolved: recovery-guide.md isolation and guard corrections present",
    "P2 resolved: archive-refresh.json note distinguishes dcbea95d initial refresh from f6e9450d native receipt",
    "No remaining blocker for guide or label; conditional forget passes after parent live checks"
  ],
  "manualNotes": "Conditional forget may run only after parent live pre-checks (name target, op, unchanged refs, live config-id hash) and final Lead coordination. Use exact command without --include-remotes. A/B/remotes remain unapproved."
}
```
