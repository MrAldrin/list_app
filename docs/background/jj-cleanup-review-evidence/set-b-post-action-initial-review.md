# Set B post-action static receipt audit (read-only)

Verdict: **BLOCK (narrow)**. The executed Set B receipts pass every check. The frozen manifest field `proposed-exact-sets.json` → `B-alternates.heads` does not equal before-minus-removed heads, so that manifest claim must be corrected or explained before B review can PASS. No evidence shows the executed state is wrong.

Method: `python3 -I -B /tmp/setb-audit-scripts/audit.py` (plus `shape.py`, `keys.py`, `shape2.py`, `diffheads.py` in the same scratch directory). Scripts were written under `/tmp`, not in the repository. They only read the 20 private files and the three public JSON inputs, using `json`, `pathlib`, `hashlib`, `collections`. They run no jj, Git, subprocess, network, env, or config access, and import or execute no supplied method.

## Results (computed)

- **Index integrity:** 20 files listed, exactly matching the private directory. Each file's bytes and SHA256 match the index. Public `set-b-preflight.json` and `set-b-execution.json` are byte-identical to the private copies.
- **Commands:** step 1 `jj abandon -r d8e8f9946cce76c82c06ad6c2533cc213a42ca2c`, step 2 `jj abandon -r 31077a91123572b05e77baa41be804c6347967bb`. Both exit 0 with empty stdout. Command receipts match `execution.json`. Clean-status receipts are byte-identical (4 files, exit 0, "no changes"). Operation chain: before → step1 pre → step1 post = step1 state = step2 pre → step2 post = step2 state = `after.json` = execution post.
- **Membership:** B-alternates commits, `exact_removed_commits`, and preflight candidates all equal {d8e8f994, 31077a91}. Retained siblings are d8→c5ce1c84 and 31077a91→22ee5525.
- **Heads / conflicts / divergent:**
  - before: 18 heads, 3 conflicts, 4 divergent.
  - step 1: 17 heads, 3 conflicts, 2 divergent. Heads equal before minus {d8}.
  - step 2 / after: 16 heads, 2 conflicts, 0 divergent. Heads equal before minus {d8, 31077a}.
  - Conflict and divergent lists equal the inventory flags at every state.
  - Visible counts: 983 → 982 → 981.
  - No surviving child has a removed parent.
- **Native inventory diffs (before minus removed):**
  - step 1: only c5ce1c84 `divergent` True→False.
  - step 2: only c5ce1c84 and 22ee5525 `divergent` True→False.
  - No other field differs.
- **Git commit map:** step 1 equals before minus {d8}, and step 2 equals before minus {d8, 31077a}, with full entries compared. Before has 982 real entries, all `physical_commit_oid_verified=True`. The zero root `0000…` is separate, marked `native_synthetic_root_no_git_object: True`, and is not counted as a real Git entry.
- **Unchanged protected fields (step 1 and step 2 equal before):** bookmarks, tags, workspaces, workspace_commits, held_commits, critical_refs, working_tree, config_id, original_config_metadata_sha256, archive_resume_sha256, protected_tree_sha256 (79 entries).
- **Counts:** 79 protected trees, 36 archived resumes, 11 prior A retired trees. Archive SHA is `e703ef…604d`, recorded unchanged. `restore_rerun_this_phase` is False.
- **Retained descendants:** c5ce1c84 has 136 (before = step1 = step2 = preflight). 22ee5525 has 128 (same). Both retired commits had no descendants.
- **Preflight/diff hashes:** `pair-*.diff` SHA256 matches the preflight records.

## Finding (blocks PASS)

`proposed-exact-sets.json` → `B-alternates.heads` (16 entries) is not before-minus-removed.
- Missing from the manifest list, but present in before: `eb597a69…` and `fa1e9933…` (workspace working-copy heads).
- Present in the manifest list, but absent from before: `343493e0…` and `3fd900f4…`.
- The manifest's `combined_remaining_heads` count (16) is therefore correct, but its list is not. The list appears to come from a different source (the A-phase head set).
- Executed `after.json`, step-02 state, and `preflight.json` `predicted_heads` all equal before-minus-removed. The executed state is correct. The manifest field is wrong.

## Limits and not checked

- Static receipt validation cannot prove that no unrecorded command ran.
- `descendant-preflight-stop.json` was checked only for presence and byte hash. Its content was not analysed, and no B action is attributed to it. `preflight-review.md` was checked for a PASS string only.
- No native `jj` rerun, no live-state check, no test run.
- Model and tier: not verified by this agent. The parent must confirm the effective host model/tier (requested `claude-haiku-5-5:xhigh`).

```acceptance-report
{
  "criteriaSatisfied": [
    {"id": "criterion-1", "status": "satisfied", "evidence": "Read-only audit only; no repository or input edits; scratch scripts in /tmp; no jj/Git/network/subprocess."},
    {"id": "criterion-2", "status": "satisfied", "evidence": "Computed checks listed above, with counts; 103 checks from audit.py, 102 PASS and one FAIL on manifest heads field."}
  ],
  "changedFiles": ["/home/hsa/.pi/agent/sessions/--home-hsa-projects-list_app-jj-cleanup--/subagent-artifacts/outputs/e8b50939-8303-4dac-aef4-260ebf772384/jj-cleanup-set-b-post-action-static-audit.md"],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {"command": "python3 -I -B /tmp/setb-audit-scripts/audit.py", "result": "failed", "summary": "All executed-receipt checks pass; one FAIL: B-alternates.heads manifest list != before-minus-removed."},
    {"command": "python3 -I -B /tmp/setb-audit-scripts/diffheads.py", "result": "passed", "summary": "Diagnosed heads diff: manifest omits eb597a69/fa1e9933, includes 343493e0/3fd900f4; executed after heads match expected."},
    {"command": "python3 -I -B shape/keys/shape2 inspection scripts", "result": "passed", "summary": "Structure inspection only."}
  ],
  "validationOutput": [
    "20/20 index files bytes+sha256 match; public preflight/execution byte-identical to private",
    "step1 17 heads/3 conflicts/2 divergent; step2 16 heads/2 conflicts/0 divergent; visible 983->982->981",
    "native diffs: step1 only c5ce divergent; step2 only c5ce and 22ee divergent",
    "retained descendant sets 136 (c5ce) and 128 (22ee) identical before/step1/step2/preflight"
  ],
  "residualRisks": [
    "Manifest heads field wrong (blocks PASS until corrected)",
    "Static validation cannot prove absence of unrecorded commands",
    "descendant-preflight-stop.json checked by hash only"
  ],
  "noStagedFiles": true,
  "diffSummary": "No repository diff; one audit artifact written.",
  "reviewFindings": [
    "blocker: docs/background/jj-cleanup-review-evidence/proposed-exact-sets.json B-alternates.heads - list differs from before-minus-removed (omits eb597a69, fa1e9933; includes 343493e0, 3fd900f4)"
  ],
  "manualNotes": "Model/tier to be verified by parent host: requested claude-haiku-5-5:xhigh. Scratch scripts live in /tmp/setb-audit-scripts."
}
```

Implemented: Read-only static audit of Set B receipts. Verdict BLOCK (narrow).
Changed files: artifact only (this file). No repository or input edits.
Validation: `python3 -I -B audit.py` ran 103 checks, 102 PASS and 1 FAIL (111 output lines). The failing check is the manifest heads field.
Open risks/questions: The frozen manifest `B-alternates.heads` list must be corrected or explained. Static validation cannot prove absence of unrecorded commands.
Recommended next step: Correct `proposed-exact-sets.json` B-alternates heads to before-minus-removed, then re-run the audit for PASS.

