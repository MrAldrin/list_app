# Escalated independent static review: targeted jj cleanup

Reviewer: `86787486-dbdf-4ee8-8978-d160129c1218`, requested `claude-code/claude-haiku-5-5:max`.
I cannot attest my own thinking tier; the parent must confirm it from host status.

## Boundary observed

- No jj, Git, or remote command was run, and no config, workspace, or bookmark was touched.
- Evidence came from reading the files and from bounded Python (`python3 -I`) that only read JSON and computed hashes.
- The archive was read once: a streamed SHA-256, a stat, and a tar member listing. Nothing was extracted, and no copy was made.
- The steering-reported live op `386bc408` and the Lead's repair receipt were not independently verified.
- Receipts I did not rerun: restore, 988/1024 matches, the trace validation, the native disposable A/B simulation, and the budget measurement.

## Overall

| Item | Verdict |
| --- | --- |
| Conditional local forget of `reminders-s2` (`e50da7ce`) | **PASS (static)**, after the parent's own live pre-check (below) |
| Set A (11 empties, 28→18 heads) | Membership and arithmetic verified static; **owner approval still required** |
| Set B (2 divergent leaves, 18→16 heads) | Verified static; **owner approval still required** |
| Remote deletion, tracking changes, `integration@origin` | Correctly blocked; not approved |
| Recovery inspection guide (`recovery-guide.md`) | **FAIL (P1)** until isolation gaps are fixed |
| Receipt labelling (`archive-refresh.json`) | **P2** correction required |

## Verified statically (independent)

1. **Archive hash and size.** A streamed SHA-256 of `native-history.tar` equals `e703ef0567c351c41f195603656c297af08290d7063cafdf41181fa24ffb604d`, and the size is 160,430,080 bytes. The archive contains 50,513 members (`.jj` 26,344, `.git` 24,169), with no symlinks, hardlinks, `..` or absolute paths, and no `objects/info/alternates`.
2. **Raw review transcription error.** `blocked-luna-review.md` contains a 66-character token that starts with the correct prefix but is not the 64-character hash. The disposition's correction is accurate. The raw review stays as failure evidence.
3. **Manifest P2 correction.** `proposed-exact-sets.json` now matches the 988-record, 28-head inventory:
   - A: 18 heads, 977 visible (`combined_remaining_*`); computed from `current-inventory.json` matches exactly.
   - A+B: 16 heads, 975 visible.
   - A+B+C: 15 heads, 971 visible.
   - Survivor arrays equal the computed heads. Memberships are unchanged, and no surviving child has a removed parent.
4. **Membership and tail structure.** All 11 A commits match the inventory's change ID, parents, empty flag and conflict flag, and each has the stated descendant count. `95b1f504` has one child (`095fe95`), which is also in the set. Both B leaves are current heads with parent `6afb105c` and zero descendants. `31077a91` is conflicted; `d8e8f994` is not.
5. **Retained descendants.** `c5ce1c84` has 143 descendants, `22ee5525` has 135, and `6addc911` has 153. `fb60a3d8` has a nonempty parent `cd32f708`, which confirms the exclusion.
6. **Conditional local name.** `e50da7ce0a5456159f8206513c820e7180abbb8e` is an ancestor of `main` (`250c17b6`). Its only parent is `b2bd7bba`. The disposable forget and the restore command are exact.
7. **Remote and origin claims.** `live-origin.json` names the five server tips, and `ddd687e2` (`origin/integration`) is an ancestor of local `integration`. The 139-commit gap and the 25-commit lead of `integration` over `main` both check out. `usual-items` (`3d1b2711`) and `wave2` (`85c93c34`) are not in `main`, but both are reachable from the preview `aa6c85da`. `groups` has 5 unique commits over base `391b36fd`, which is in `main`.
8. **Budget.** The `budget-and-links.json` roots sum to 2,693,820,416 bytes, below 3,221,225,472. Free space of 13,302,497,280 is above the 6,442,450,944 floor. The later small receipts are not re-measured.
9. **Resume rows.** `archive-refresh.json` has 36 entries; 26 have visible versions and 10 are hidden-only. All 36 resolve.
10. **Head table.** `head-decisions.md` has 28 head rows, matching the inventory's 28 computed heads.
11. **Report links.** All local links in `jj-cleanup-review.md` resolve.

## Findings

**P1 — `recovery-guide.md` isolation is incomplete before any jj read.** The guide's only isolation variables are `HOME`, `XDG_CONFIG_HOME`, and unsets of `JJ_CONFIG` and the GIT variables. Three gaps remain:
- `XDG_DATA_HOME`, `XDG_STATE_HOME` and `XDG_CACHE_HOME` are not redirected, so jj may write to the live user directories.
- The per-repo config copy that the earlier incident created sits under the user's `~/.config/jj/repos`. The guide does not check that path before or after launch.
- The guide's `python3 -c` check runs without `-I`. Per the environment rule, Python that reads untrusted extractions must use `-I`, and the guide does not say which directory it runs from.

Minimal fix: add `XDG_DATA_HOME`, `XDG_STATE_HOME` and `XDG_CACHE_HOME` under the isolated `home`; change the check to `python3 -I -c`, run it from a neutral directory; and record the names (metadata only, no contents) of `~/.config/jj/repos` before and after the first inspection. Use `tar --no-same-owner -xf`. Do not run the guide until these are in.

**P2 — `archive-refresh.json` names a different frozen op.** Its `frozen_op` is `dcbea95d4cd7b5a7…`, which does not match the native snapshot `f6e9450d01c4e22635b646e9038ac50980a99903124bfb7e5adc15f6a0cd878d59bf692b1032c78c83c8e49549299b02be248946281f3f58ac1328adf6ce226d`. The report does not cite this file, so the mismatch is not a claim error, but the receipt is misleading. Minimal fix: either add a `note` field saying which snapshot `dcbea95d` is and why it differs, or regenerate the receipt against `f6e9450d`. Do not reuse it as evidence of the native snapshot.

**P2 — Parent-reported live state is unverified.** The steering's live op `386bc408`, the repair's live readback, and the untouched pager process are not checked by me. The forget must not run until the parent's own live pre-check confirms the current op, `reminders-s2` → `e50da7ce`, and that `main`, `integration`, `groups` and the old refs are unchanged.

**P3 — Small inconsistencies.**
- The report's budget section says later receipts still need measuring. Re-measure before closeout.
- The A command block's header says "nine independent empty leaves, then one two-empty tail". The commands match this (9 single plus 1 two-commit tail = 11). Not a defect, but the wording could be clearer.
- The name-dependency receipt records `other_config_not_recorded: true`. The report states "configured jj aliases have no dependency", which is correct, but owner-private aliases remain uncertified, as the report says.

## Conditional `reminders-s2` local forget: answer

Yes, on static evidence it may proceed, under these conditions the parent must verify live, since I cannot:
1. Live `reminders-s2` points to `e50da7ce0a5456159f8206513c820e7180abbb8e` (change `wlwznqly`).
2. `main`, `integration`, `groups`, and the old origin refs are unchanged from the report's snapshot.
3. The current op is recorded before and after.
4. The final Lead coordination is recorded as complete.

The action is `jj bookmark forget exact:reminders-s2` only. It must not add `--include-remotes`. It does not touch commits or heads.

## Remote, A and B: blocked

- Remote deletions in `proposed-commands.md` and `jj-cleanup-review.md` are proposals only. Their `--force-with-lease=<ref>:<tip>` guards are syntactically correct. None may run without an itemized owner decision.
- The `jj bookmark forget --include-remotes` cache-only option is not approved. It would return on the next fetch while the server branches exist.
- Set A and set B commands are correctly marked not approved. The manifest now supports their review.

## Acceptance report

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "No jj/Git/remote command, workspace or config mutation; reviewed only the authoritative plan, docs, evidence files, and bounded read-only Python. Verdicts split into conditional forget PASS, A/B blocked on owner approval, guide FAIL until P1 fixes."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Independent checks: archive SHA-256 equals e703ef05...604d; 50,513 members with no links/alternates; manifest A=18/977, A+B=16/975 heads match computed inventory heads; memberships, parents, empty and conflict flags verified; descendant counts 143/135/153 verified; e50da7ce ancestry verified; budget sum 2,693,820,416 < 3 GiB; 36 resume rows (26 visible, 10 hidden-only)."
    }
  ],
  "changedFiles": [
    "/home/hsa/.pi/agent/sessions/--home-hsa-projects-list_app-jj-cleanup--/subagent-artifacts/outputs/86787486-dbdf-4ee8-8978-d160129c1218/jj-cleanup-escalated-independent-review.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "bounded python3 -I JSON/hash/tar-member reads of docs/background/jj-cleanup-review-evidence and the archive",
      "result": "passed",
      "summary": "Read-only; manifest, inventory, ancestry, budget, archive hash/member checks passed; no extraction"
    },
    {
      "command": "jj or git (any)",
      "result": "not-run",
      "summary": "Prohibited by the review boundary"
    },
    {
      "command": "native restore / recovery-guide commands",
      "result": "not-run",
      "summary": "Guide not executed; its P1 gaps must be fixed first"
    }
  ],
  "validationOutput": [
    "Archive SHA-256 e703ef0567c351c41f195603656c297af08290d7063cafdf41181fa24ffb604d, 160,430,080 bytes",
    "Manifest A 18 heads/977 visible; A+B 16/975; A+B+C 15/971; survivor arrays equal computed heads",
    "e50da7ce ancestor of main; main ancestry 745 commits including itself",
    "budget 2,693,820,416 bytes; free 13,302,497,280 above floor"
  ],
  "residualRisks": [
    "Live op 386bc408 and the repair readback are not independently verified",
    "Guide isolation gaps P1 (XDG dirs, python -I, per-repo config path check)",
    "archive-refresh.json frozen_op dcbea95d mismatches native op f6e9450d",
    "Owner-private jj aliases and external tools uncertified"
  ],
  "noStagedFiles": true,
  "diffSummary": "New review artifact only; no repository files changed.",
  "reviewFindings": [
    "P1: docs/background/jj-cleanup-review-evidence/recovery-guide.md:~35-48 - isolation omits XDG_DATA/STATE/CACHE, python3 check lacks -I, no pre-launch per-repo config name check",
    "P2: docs/background/jj-cleanup-review-evidence/archive-refresh.json frozen_op - does not match native snapshot f6e9450d",
    "P2: live op 386bc408 and repair readback not independently verified; parent pre-check required before forget",
    "P3: budget later receipts not re-measured; A command header wording"
  ],
  "manualNotes": "Conditional local forget of reminders-s2 may proceed only after the parent's live pre-check and final coordination. A, B, remote names, and integration@origin remain owner-gated. Do not run the recovery guide until P1 is fixed. Reviewer tier must be confirmed by the parent from host status."
}
```
