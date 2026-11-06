# Post-action static receipt review: `jj bookmark forget exact:reminders-s2`

Reviewer: `86787486-dbdf-4ee8-8978-d160129c1218`, requested `claude-code/claude-haiku-5-5:max`.
Tier is parent-verified; I cannot attest it myself.

## Boundary observed

- No jj, Git, network, or config-content access. No extraction. No native check was rerun.
- I read only the receipt JSON files in `docs/background/jj-cleanup-review-evidence/` and the archive directory listing (names and sizes). I used bounded `python3 -I` JSON parsing and set comparisons.
- Live post-state is parent-only. This review audits the recorded receipts and does not claim an independent live rerun.

## Verdict

**PASS as a receipt audit.** No overclaim or receipt-logic problem found. No remaining blocker for the recorded action. The owner-conditional local forget is recorded as done; A, B, remote names, and `integration@origin` remain unapproved.

## Checks against the receipts

**Operation IDs.** `before-local-forget.json` is `16f184ff…8144` and `after-local-forget.json` is `dc507677…9258`. Both match the orchestrator's stated pre and post IDs. `local-forget-command.json` and `local-forget-protected-check.json` both record the same pre and post IDs.

**Command.** `local-forget-command.json` records `jj bookmark forget exact:reminders-s2`, exit 0, with stderr `Forgot 1 local bookmarks.`. It has no `--include-remotes`. The recorded exact tip is `e50da7ce0a5456159f8206513c820e7180abbb8e`.

**Commit metadata.** `metadata_without_reference_labels` is byte-identical before and after, with 988 rows and 988 unique commit IDs.

**Workspace targets, working tree, heads, conflicts, divergence.** `workspace_targets`, `working_tree`, `heads`, `conflicts`, and `divergent` are identical before and after. Counts are 28 heads, 3 conflicts, and 4 divergent versions, all matching the protected-check record.

**Critical refs.** Eleven of the twelve critical targets are unchanged. The only change is `reminders-s2`, which goes from `e50da7ce…` to empty. Unchanged: `main`, `integration`, `groups`, `usual-items-redesign@origin`, `wave2-bottom-bar@origin`, `integration@origin`, and the five `night-*` bookmarks.

**Bookmark text.** A unified diff of the bookmark text removes exactly two lines: `reminders-s2: wlwznqly e50da7ce …` and its `@git:` line. No other line changes.

**Ancestry.** `s2_exact_ancestor_main_count` is 1 before and after.

**Protected trees.** `protected_exact_tree_fingerprints_match` lists 52 unique IDs. All 36 archived exact resume commits from `archive-refresh.json` are in that list. The receipt records these as commit IDs, not tree hashes, so the 36 resume entries' `tree_sha256` values are not in it by design. This is a note, not a defect.

**Checksums and config identity.** Both `durable_archive_sha256` and `archive_resume_sha256` (`a959fc28…`) are unchanged. Both `live_config_id` values are `73360a744b7debff796b`. `original_global_config_metadata_sha256` is `5f55d95b…` in both files. `global_repo_config_directory_names` is identical (7 names).

**Owned recovery cleanup.** `owned-recovery-cleanup.json` lists four removed paths: `staging`, `restore-test`, `restore-final`, and `isolated-home`. All four are under the recovery directory. The recovery directory listing shows those four are gone, and the retained items are present (`native-history.tar`, the receipts, both `.strace` traces, `config-id-incident`, `methods`). `shared_workspaces_removed` is empty, and `lead_created_entry_not_removed` is true.

**Budget.** `final-budget-and-links.json`:
- The root sum is 1,956,982,784 bytes, matching `final_allocated_bytes`.
- The conservative peak bound is 2,705,956,864 bytes, which is 12,136,448 above the prior measured 2,693,820,416. That is below 3 GiB (3,221,225,472).
- Free space is 14,047,449,088 bytes, above the 6,442,450,944-byte floor.
- The peak method deliberately double-counts later records plus a 2 MiB margin. It is not an exact historic measurement.
- My own bound check: the later items I can identify (three review run directories, the grown temp and evidence directories) sum to about 7.95 MB. With a 2 MiB margin that is about 10.0 MB, which is below the 12.1 MB claimed. The bound is consistent.

**JSON.** All six new JSON files parse. The report links remain resolved as previously recorded.

## Limits and residuals

- I did not rerun any native check. The protected-check, the post-state, the process checks, and the `live_config_id` value are parent-recorded.
- `owned-recovery-cleanup.json`'s `active_processes_using_removed_paths: []` and `lead_coordination` in `local-forget-command.json` are parent attestations. I did not verify them.
- The current live state is not independently checked here.
- The peak bound is conservative. It is not a measured peak.

## Remaining blockers

None for the recorded receipts.

## Acceptance report

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Only the local forget command is recorded as performed. Receipts show no remote, A, B, or workspace/entry cleanup. Review made no jj/Git/network/config-content calls and no extraction."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Compared before/after JSON: 988 identical metadata rows; heads 28, conflicts 3, divergent 4 unchanged; workspace targets and working tree identical; only reminders-s2 changed (to empty); bookmark diff removes only reminders-s2 and its @git line; e50da7ce ancestor count 1; 36/36 resume commits in 52-entry protected list; archive SHA and resume SHA unchanged; config-id 73360a744b7debff796b and global metadata SHA and config-dir names unchanged; budget root sum equals 1,956,982,784; peak bound 2,705,956,864 < 3 GiB; free above floor."
    }
  ],
  "changedFiles": [
    "/home/hsa/.pi/agent/sessions/--home-hsa-projects-list_app-jj-cleanup--/subagent-artifacts/outputs/86787486-dbdf-4ee8-8978-d160129c1218/jj-cleanup-escalated-independent-review.fcbe2181.7538d73a.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "bounded python3 -I JSON parse and set/diff of receipt files; ls of recovery directory names",
      "result": "passed",
      "summary": "Receipts consistent; no jj/Git/network/config access; no native checks rerun"
    },
    {
      "command": "native jj/Git commands",
      "result": "not-run",
      "summary": "Prohibited by this review boundary"
    }
  ],
  "validationOutput": [
    "before op 16f184ff…8144 -> after op dc507677…9258",
    "988 identical metadata rows; heads 28, conflicts 3, divergent 4 unchanged",
    "only reminders-s2 critical ref changed; bookmark diff removes only its local and @git lines",
    "36/36 resume commits in 52-entry protected list; durable archive SHA e703ef05…604d unchanged",
    "config-id 73360a744b7debff796b unchanged; global metadata SHA 5f55d95b… unchanged; 7 config-dir names unchanged",
    "budget root sum 1,956,982,784; peak bound 2,705,956,864 < 3,221,225,472; free 14,047,449,088 > 6,442,450,944"
  ],
  "residualRisks": [
    "Live post-state, process-absence and coordination claims are parent-recorded, not independently verified",
    "Peak budget is a conservative bound, not a measured peak",
    "Protected list records commit IDs; resume tree hashes are not in it by design"
  ],
  "noStagedFiles": true,
  "diffSummary": "New review artifact only; no repository files changed by this review.",
  "reviewFindings": [
    "no blockers: receipts internally consistent; no overclaim found in action, owned cleanup, or budget claims"
  ],
  "manualNotes": "PASS as a receipt audit. A, B, remote names and integration@origin remain unapproved; no further work requested."
}
```
