# Material-fix independent re-review — scoped APPROVE

Reviewed the actual `c80399eb..b4fb139b` diff, author result and prior blocker against the current quiescent workspace. Exact reviewed tip is `vwumlnzl b4fb139b`, parent `qnuqpxvz/0 c80399eb` (divergent ID left untouched), original core base `a9a87d5f`. Approval is limited to the internal non-sending scheduler/generation slice; it is not approval of API, dispatch, push, claim/send fencing, or full S3.

## Findings

**No blockers found in this fix.** The original single-scope false-ready reproduction is covered by `tests/test_reminders_scheduler.py:262-291`: four successive failure and empty-wrap ticks remain `SCOPE_ERROR` with no `last_success`, followed by a real successful retry and a clean wrap. The implementation at `src/reminders/scheduler.py:122-130,164-172` latches faults across batches and wrap pages and only clears them after a subsequent clean sweep; a wrap never advances `last_success`. Partial-batch failure preserves the previous successful time, and deletion of a failed enrollment can clear the fault after a clean sweep. Local-runtime versus production configuration and lifecycle-hook documentation were clarified.

Independently exercised two failing scopes on different one-scope pages against the existing real SQLite fixture: removing the first did not clear the second fault; after removing the second, the status stayed faulted through processing and cleared only on the clean wrap. Output for final ticks: `[('scope_error', 1), ('scope_error', 1), ('ready', 0), ('ready', 1)]`. The existing async serialization, cancellation wait, and lifespan/health tests pass; shutdown and concurrency implementation are unchanged by this fix. This is not proof of every possible thread interleaving or external deployment environment.

## Commands and evidence

- `pwd`, receipt environment, `jj status`, `jj log -r 'b4fb139b | c80399eb' --no-graph`, `jj diff --from c80399eb --to b4fb139b`: requested workspace and exact tip/parent confirmed; `PI_PROVIDER=openai`, `PI_MODEL=gpt-6.1-terra`, `PI_REASONING_LEVEL=medium`.
- `uv run pytest -q -n 0 tests/test_reminders_scheduler.py tests/test_reminders_generation.py tests/test_reminders_storage.py tests/test_reminders_restore_state.py`: **138 passed**.
- Five focused status-recovery, partial/removal, tick serialization, cancellation, and lifespan/health tests: **5 passed**.
- `PYTHONPATH="$PWD/src:$PWD/tests" uv run pytest -q -s -o addopts='' /tmp/test_scheduler_review_342406ba.py`: **1 passed**, real-SQLite staggered two-fault removal scenario. This test was created outside the repository and is not a proposed source change.
- `git diff --check` passed; `git diff --cached --quiet` returned zero, no staged files. No source, docs, or jj edits were made. The author's full-suite 1926 passed/9 skipped result was read, not independently rerun in this re-review.

## Remaining integration limits

The existing restore reconciliation drains bounded SQL batches inside one scope transaction, so lock hold and shutdown wait may grow with backlog. Restore snapshots are not a final send fence. Delivery, claim authorization and fencing, full S3 integration, and real deployment remain outside this review. No network, production service, or real notification was used.
