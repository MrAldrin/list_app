# Set B provenance correction: static check (partial, BLOCK)

Verdict: **BLOCK (incomplete)**. The provenance BLOCK is NOT closed. The single bounded `python3 -I -B` heredoc crashed before the head recomputation, so the requested equalities were never evaluated. The original narrow BLOCK stays in force and is not relabeled.

## Run

One `python3 -I -B -` heredoc, reading only the inputs named in the follow-up. No jj, Git, config, env, network, subprocess, or source/temp writes.

Hashes computed by the run:
- Parent map `historical-f6-parent-map.json`: 101057 bytes, SHA256 `217918abf567e575811a3bae800012c74fcf5442f0aa5161a296a9a055537116`. **Matches the sidecar** `historical_native_parent_map_sha256`. This is the only check that completed.
- `proposed-exact-sets.json`: SHA256 `e891b74e15bc090002ad55c696821695e60a8bff40e8881d8ac925d9dd257e49`.
- `current-workspaces.txt`: SHA256 `7e8285c66779eb6f16e5eb63819623e157f4963aa6344d87de05d37f3736d1b5`.

Completed output:
- PASS parent map sha256 matches sidecar.
- PASS historical f6 map has 988 entries including the zero root.

The run then crashed at `heads_of` with `TypeError: list indices must be integers or slices, not str`. The traceback shows the map's values are lists, not native row objects. The top-level keys are commit IDs, and each value is a parent-ID list. The script assumed `inv[k]["parents"]`, so it did not run. The top-level output was also very large, because the script printed every key.

## Not evaluated (no result)

- Historical after-A11/B2 heads recomputation (expected 975 visible, 16 heads, equal to manifest `B.heads`).
- Current before-minus-B2 heads, equal to after.json and preflight (981 visible, 16 heads).
- Exact two-ID head delta (`343493e0`/`3fd900f4` vs `eb597a69`/`fa1e9933`) and the 14 unchanged IDs.
- Lineage of replacements `dc6d14e6` and `37fedeec` to current heads.
- Unexplained-delta check over f6-only and before-only ID sets.
- Workspace owner labels in `current-workspaces.txt`.

## Finding to resolve before any PASS

The historical parent map appears to store parent-ID lists per commit, not the full native rows (change ID, description, empty/conflict/divergent flags) that the provenance sidecar says it contains. The sidecar's old-row claims (`343493e0`, `3fd900f4`, and the `dc6d14e6` and `37fedeec` replacement rows) therefore cannot be checked against this map as stated. Confirming them requires the parent to name the file that holds full f6 native rows, or to state that the map is parents-only. This is a source-of-truth question, not a computation.

## Limits

- Native historical reads and the parent map were produced by the parent under the pinned operation. This run does not independently verify them against jj.
- The executed-state checks from the earlier audit (102 PASS) stand. They are not re-run here.
- Model and tier: host-verified by the parent, not by this agent.

```acceptance-report
{
  "criteriaSatisfied": [
    {"id": "criterion-1", "status": "not-satisfied", "evidence": "Provenance correction not completed; crash before head recomputation and lineage checks."},
    {"id": "criterion-2", "status": "satisfied", "evidence": "Crash, hashes and partial output recorded verbatim above."}
  ],
  "changedFiles": ["/home/hsa/.pi/agent/sessions/--home-hsa-projects-list_app-jj-cleanup--/subagent-artifacts/outputs/e8b50939-8303-4dac-aef4-260ebf772384/jj-cleanup-set-b-post-action-static-audit.1a24f9f4.md"],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {"command": "python3 -I -B - (single heredoc, provenance static check)", "result": "failed", "summary": "Parent map sha256 PASS and 988-entry PASS; crashed at heads_of (map values are parent lists, not row objects). No head, lineage, or delta checks completed."}
  ],
  "validationOutput": [
    "parent map sha256 217918ab... matches sidecar",
    "historical f6 map 988 entries incl zero root",
    "TypeError in heads_of: list indices must be integers or slices, not str"
  ],
  "residualRisks": [
    "Provenance BLOCK remains open; no head or lineage equality established",
    "Historical parent map may be parents-only; sidecar full-row claims unverifiable from it",
    "Static check cannot prove absence of unrecorded commands"
  ],
  "noStagedFiles": true,
  "diffSummary": "No repository or input edits. One artifact written.",
  "reviewFindings": [
    "blocker: docs/background/jj-cleanup-review-evidence/set-b-head-provenance.json - historical_native_parent_map_path content is parent-ID lists, not native rows; sidecar full-row claims not verifiable from it"
  ],
  "manualNotes": "Single-heredoc constraint honored; no second run. Rerun needs the parent's decision on the row source, and a corrected script."
}
```

Implemented: Partial provenance static check. Verdict **BLOCK (incomplete)**.
Changed files: this artifact only.
Validation: One `python3 -I -B` heredoc. Parent map SHA256 matches the sidecar, and the 988-entry count passes. It then crashed at `heads_of` because the map holds parent-ID lists, so no head, lineage, or delta equality was checked.
Open risks/questions: Does the parent map hold only parent IDs, with full native rows stored in another file? If so, name that file. A corrected rerun needs your approval under the one-heredoc rule.
Recommended next step: Confirm the row source for historical f6 native rows, then authorise one corrected static run for the head, lineage, and delta checks.
