# Escalated Static Preflight Review: Set A (01a1afc6)

## Scope and limits

- Static review only. I read only the five assigned files, with the read tool.
- I ran no jj, Git, shell, network, browser, env, or config reads. I did not run `preflight`, `execute`, or any `jj abandon` command, and I made no edits or fanout.
- Live commands status: **NOT RUN** by me. I did not verify on-disk repository state, the archive file, the 67 protected-tree count, or the 36 archived-exact entries. Those need the parent's native checks.
- Model: I am claude-haiku-5-5. I cannot verify the requested `claude-code/claude-haiku-5-5:max` tier. The parent must verify it.

## Review

- **Correct: prior P1 is closed.** The old inventory kept only the first description line and lacked full commit metadata. Now `inventory()` (set_a.py:35–50) records full native descriptions. `complete_git_objects()` (set_a.py:52–78) reads every visible Git commit body with `cat-file --batch` and checks SHA1(`commit <size>\0<body>`) against the commit ID. It records a SHA256 of the full raw body and the explicit tree ID. `compare()` (set_a.py:91–96) requires strict equality of both sets, minus only the removed IDs. The raw-body hash covers author, committer, timestamps, signatures, and full message. The tree ID is covered by the body hash and by the separate tree check.
- **Correct: exact commands match the manifest.** `STEPS` (set_a.py:17) yields nine single-ID abandons followed by one two-ID tail `[095fe…, 95b1…]`. This matches `preflight.json` `commands` and `proposed-commands.md` section A. B-section retirements, `bookmark forget`, and the C section are not in the script.
- **Correct: operation ID matches.** `preflight.json` `operation` (877827c0…e51) equals the graph operation given in the task.
- **Correct: the only mutation is `jj abandon` with exact IDs.** Every read uses `--ignore-working-copy` and `--at-op`. There is no `gc`, `git gc`, `bookmark`/`remote` mutation, immutable override, or broad selector. The `execute` path asserts full-state equality with the prior step before every operation, then checks the new state and head count after it.
- **Correct: graph safety checks.** `preflight` asserts that no selected commit is held (bookmark, remote bookmark, tag, or working copy) or an ancestor of a critical ref. It asserts each selected commit has the expected children (none, except `95b1`→`095fe`). It asserts predicted heads are a subset of current heads, so no parent is exposed. It also checks archive SHA, free space, and `archive_resume` SHA.
- **Correct: per-step fail-closed behavior.** Any mismatch raises an exception. The only mutation runs after the pre-check, and a failed command stops the run.

**Finding — P2 (report-only): `jj abandon` snapshots the working copy and is not guarded.** `execute()` (set_a.py:~122) runs `jj abandon` without `--ignore-working-copy`. The pre-state capture uses `--ignore-working-copy`, so disk-only edits are invisible before the mutation. Preflight never asserts a clean working copy. If the disk differs from `@`, the abandon command itself creates a new `@` commit. The post-state check then fails, but only after the mutation. This fails closed but gives a mid-run stop. Smallest fix: before step 1, check that `jj status` reports no changes to the working copy, or assert that `@` is empty and unchanged on disk.

**Finding — P2 (report-only): protected-tree readback of removed commits is untested.** After step 1, `capture()` recomputes `debug tree` for protected IDs, which can include removed commits if they are in the 36 archived set. `debug tree -r <hidden commit>` under `--at-op` may fail. The script then raises after one mutation, with no receipt for the failure. This is fail-closed. Smallest fix: before any mutation, run `tree()` on all 11 selected commits at the pre-op and confirm they resolve. The live parent can verify this with a read-only check.

**Limit (not a finding): hardcoded store path.** `complete_git_objects()` hardcodes `/home/hsa/projects/list_app/.jj/repo/store/git_target`. It assumes `HERE` shares that store. I could not verify this statically.

**Limit (not a finding): budget.** The 64 MiB receipt limit is checked before each mutation, but the final `after.json` and `execution.json` writes are not checked. The total size is not verifiable statically.

## Merge verdict

**PASS (static only), with notes.** The prior P1 guard gap is fixed. Blocking: none found. Live execution still requires the parent's exclusive-window native verification, and the two P2 notes should be addressed or accepted before running. This is not a live authorization.