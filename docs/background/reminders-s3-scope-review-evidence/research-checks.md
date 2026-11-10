# Task 5 checks and limits

## Fresh historical snapshot check

- Exact source parent: `216b2eabfd25b6467d64e97906601879ad723084`
  (`vtlptvvslvno`, current visible version of archived joined component
  `8743a470f23f2e246e6a2937c1bf7ab5b67105cb`).
- Disposable workspace: `night-s3-review-snapshot`, empty child `nsxuyuvt` /
  `2f94b979`. Its source was unchanged before and after the run.
- Command/environment: [retained runner](run-historical-check.sh).
  Existing development environment, `uv run --offline --no-sync`, no install.
  `env -i`, `PYTHON_DOTENV_DISABLED=1`, `DB_PATH=:memory:`, synthetic app
  password, push off and reminders off unless a test explicitly overrides it.
  No `.env` was copied or linked. The inspected fixtures use memory and
  pytest temporary SQLite/files. No listening server or external sender ran.
- Four complete modules: generation, scheduler, strip claim, restore state.
- Result: **150 passed in 18.18 seconds; exit 0; zero skips reported.**
  [Log](historical-check.log), [exit code](historical-check.exit).
- Purpose: determine whether archived summary generation, durable claim,
  revocation and recovery building blocks can still be exercised. These
  passed tests support retaining the components as evidence/design inputs.
- Limits: historical source only, under the current shared dependency
  environment. Not a full historic environment reproduction, current accepted
  compatibility test, new foreground-summary test, browser test, whole-S3
  approval or phone observation. No failure was repaired or retried.
- Cleanup: finished pane 79/tab 24 closed after exit 0 verification. The clean
  snapshot was forgotten with jj and its folder removed. Its 42,194,635 bytes
  of fully passed temporary files were removed after saving the logs. Exact
  historical sources and all prior failure evidence remain untouched.

## Baseline fit, freshly inspected

Accepted behavior is frozen at `9e34df13e5b773ebf88032047fbe26a1088877bb`,
not the execution stack or parked S3. [File hashes](baseline-fit-manifest.json)
and [focused diff size](historical-vs-accepted.stat) compare it with the exact
historical snapshot. This selected reminder seam has 51 changed files,
11,503 insertions and 260 deletions, including tests. Size is not effort or
quality evidence by itself.

Concrete mismatches:

- Accepted `preview.py` exports `_quiet_end`; archived generation imports
  `quiet_end`. Accepted preview has no overdue-repeat arguments.
- Archived identity adds grant epochs, cancellation, repeat activation,
  snooze/quiet and frequency reconciliation. Accepted identity has none of
  those hooks. Archived policy writes call a new runtime lifecycle module.
- Accepted migrations end at 18; the joined archived runtime includes 19–28.
  Never register historical versions blindly on the current app.
- Archived server adds a lifespan scheduler. Accepted server has no scheduler.
- P2's one-line false settings switch exists at the accepted baseline; it is
  absent in this archived combined source. Copying old UI would bypass P2.
- `rules.py`, `zoned_time.py` and `src/api/reminders.py` match byte-for-byte
  across these exact refs. This supports reusing the accepted versions, not
  replacing them with an old runtime tree.

## Inherited evidence, not fresh tests

Three original review/gate reports are copied without content changes under
[inherited-reviews](inherited-reviews/). Their original paths and SHA-256
values are in [the manifest](inherited-review-manifest.json). They describe
bounded scheduler, UI and combined component work. Their historical counts
are not included in Task 5's fresh 150-test count. The runtime owner/checkpoint
records still say incomplete, paused and not accepted.

[Exact version comparisons](reviewed-version-comparisons.json) freshly compare
reviewed archived scheduler `b4fb139b` to inspected `bc62f6d5`, UI `ef49557f` to
`ff2d4ddb`, and joined `8743a470` to `216b2eab`. Each differs only in historical
plan/background records, not executable source or tests. This connects the
inherited scoped reviews to inspected source bytes; it does not expand their
approval scope or turn historical checks into fresh checks.

## Setup failures

The first setup used unavailable `python`; it exited 127. A jj template using
`root_tree_id`, and a later read-only template using `id`, were unsupported.
The commands were corrected after inspecting installed help. No protected
source, archive, bookmark or other workspace changed. A protection JSON file
exceeded jj's new-file size limit; it was split into a compact state record
and the archive TSV, without changing repository config.
