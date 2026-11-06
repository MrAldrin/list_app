# S3 scope and recovery review

Lifecycle: tracked

## Status and outcome

The owner approved this research assignment within the [overnight run limits](night-run.md).
That record owns sequencing, stack destination, and operating limits. Task
ownership is assigned at dispatch. This plan does **not** authorize S3
implementation or resume stages 4 and 5.

Inspect the archived S3 work and the accepted app. Recommend the smallest
useful in-app reminder feature for about five users. Give the owner a short,
evidence-backed document that makes the scope decision easy.

The [backlog](backlog.md#next) owns the agenda. The
[master reminders plan](due-date-reminders.md) and
[existing S3 brief](batches/reminders-s3.md) describe the earlier scope; they are
inputs, not permission to restart that scope. The master's later hold and
current owner decisions take precedence over historical execution approvals.

## Questions to answer

1. What useful behavior would the user gain beyond the existing due bell and
   due times? Which parts are visible only while using the app, and what must
   not be promised about background or phone delivery?
2. What is the smallest coherent S3 release? Which advanced scheduling,
   summaries, snooze, repeats, history, and manual actions should be retained,
   deferred, or dropped? Explain each choice in user terms.
3. Which archived components are implemented, reviewed, tested, compatible with
   the current baseline, and actually reusable? These are separate judgments.
4. Would recovering a component be simpler than rebuilding a small version?
   Include compatibility, security, testing, and maintenance costs, not just
   how much code already exists.
5. Which protections remain essential even after reducing features: device and
   room isolation, revocation, privacy, duplicate suppression, and safe recovery?
6. What must happen before exposing the personal settings hidden by P2? Include
   the deferred UX polish and the paused browser tests in the
   [S3 brief](batches/reminders-s3.md#deferred-polish-from-p2).
7. What does each option mean for later phone push and final polish (S4/S5)?
   Identify trade-offs without building speculative infrastructure now.

## Evidence and investigation

Start from the accepted development baseline and inspect repository status.
Do not assume the old brief, archived summary, or a passing test count proves
that a feature is complete.

Read:

- `AGENTS.md`, `docs/scope.md`, and `ARCHITECTURE.md`.
- Current reminder behavior and the master plan's product and staging decisions.
- `/home/hsa/projects/reminders-archive/resume-points.md`, including its rebase
  note, plus `s3-runtime/OWNER-SUMMARY.md` and `s3-runtime/CURRENT.md`.
- Relevant deadline/review records under that archive, then the actual source
  and tests for components considered for reuse.
- [P2 validation and cleanup](../docs/background/reminders-p2-validation.md).

Verify archive paths before relying on them. Locate moved records rather than
silently assuming a missing file means work was lost. Use current change/commit
IDs and ancestry checks; old commit IDs may be obsolete after rebases.

Build a focused recovery table:

| Component | Exact source reference | Implemented | Review evidence | Test evidence | Current-baseline fit | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |

Prioritize components relevant to the smallest release. Inventory the remainder
at a higher level. Do not spend the whole night validating code for features
that the recommended option would not use.

Distinguish inherited claims from checks performed in this review. Where a
small targeted test run would materially change the recommendation, run it on
a disposable isolated snapshot and record the exact source, command, and result.
No full historical browser matrix or revival of all old workspaces is required.
If evidence remains uncertain, say so.

## Decision report

Write `docs/background/reminders-s3-scope-review.md`. Mark all proposed behavior
as proposed, not current app behavior. Put a one-screen owner summary first;
keep the detailed recovery table and source evidence below it.

Compare at most three coherent options:

- The smallest useful in-app release, with explicit exclusions.
- A modest extension, only if it offers a meaningful extra benefit.
- Deferral, with its benefits and costs, if no small release is worthwhile.

For each option state:

- User benefit and a short example of use.
- Included and excluded behavior, including open-app/background limitations.
- Settings and UI implications, including P2's deferred work.
- Reuse versus rebuild choices and the evidence behind them.
- Essential protections and high-value acceptance tests.
- Relative effort, uncertainty, and impact on S4/S5. Avoid exact delivery
  promises unsupported by investigation.

Recommend one option. List only material owner decisions, each with a default
recommendation and the consequence of choosing differently. Separate ordinary
implementation choices that a future agent can decide without owner input.

For the recommended option, outline small implementation slices and acceptance
checks. This is a draft for a later approved implementation brief, not authority
to implement it. Do not create another competing work queue.

## Authority and exclusions

Once the review is explicitly launched, the agent may inspect archived records,
repository history, actual source, and tests; create its own isolated workspace;
run bounded local checks; and write the report. Research does not authorize
product changes.

- No code implementation, migration, settings reactivation, test weakening, or
  changes to the current product contract.
- No cherry-picking, merging, rebasing, abandoning, or cleaning up parked S3
  lines. Do not change another workspace's revision or edit archived evidence.
- No integration/main/feature bookmark moves, pushes, deployment, live enrollment,
  real notifications, production data, or service configuration changes.
- Do not change the frozen S3 brief, master scope, S4/S5 briefs, or backlog without
  an agreed docs-desk window. Present recommendations first.
- Do not launch heavy browser tests while the test-suite task is profiling.
  Agree a check schedule if needed. No preview server is required.
- If components or records cannot be recovered confidently, report the gap and
  recommend the smallest safe next step; do not repair the graph as a side task.

## Review and morning handoff

Have a fresh reviewer check that the recommendation follows the evidence,
separates reported from verified results, preserves essential protections, and
does not mistake existing S1/S2 behavior for a new S3 feature.

The morning handoff must contain:

- The owner summary, recommendation, and a short list of decisions needed.
- Report path and recovery table with exact source references.
- Checks actually run, their results, and important evidence gaps.
- The proposed implementation slices, exclusions, and acceptance criteria.
- Reviewer findings and disposition.
- Change IDs, workspace/agent ownership, artifacts retained, and cleanup state.

The work is complete when the owner can make a scope decision from the report,
not when S3 is implemented. Wait for that decision before starting any code work.

## Execution record

- Priority, difficulty, and selected Conductor: see the [backlog](backlog.md#next).
- Execution approval: [overnight run](night-run.md#approval-and-outcome); research only.
- Conductor: `01a1ae93-3d85-77d1-a29d-547cc0850af5`, verified
  `openai/gpt-6.1-sol`, `high`; Zellij tab 24, pane 78
  (`list_app-night-s3-review`).
- Large batch: product-scope analysis, exact archived-source recovery,
  current-baseline fit, reuse/rebuild evidence, and fresh independent review.
- Workspace: `night-s3-review`, `/home/hsa/projects/list_app-night-s3-review`;
  Lead-created and managed. Execution stack base: `night-4-history`
  (`xqptskso` / `4a33175a`), joined with the current docs desk. Behavioral
  comparison must use accepted `integration`, not treat stacked candidates or
  archived code as accepted. Record its exact dispatch baseline in the report.
  Lead owns entry lifecycle; Conductor owns children. Lead report target:
  `01a1ad8b-c485-774e-bb47-66e425c18dc4`.
- Work window, concurrency, and artifact budget: [overnight run limits](night-run.md#run-limits-and-defaults).
- Exclusive graph coordination passes to Conductor at dispatch. All earlier
  tasks are quiescent. At most two bounded workers/reviewers; no competing
  heavy checks. No preview server is needed. Existing docs server 38/8765 and
  gallery server 72/8766 remain untouched.
- Reuse the task 4 exact source map and protection evidence. All 36 archived
  exact resume commits resolve. No parked line, archive, existing bookmark,
  conflict, divergent version, or other workspace may be changed.
- Result: `wlyxnswq` / `55108d0d`, bookmarked `night-5-s3-review`;
  complete as research, not implementation. Report:
  `docs/background/reminders-s3-scope-review.md`; evidence sibling
  `reminders-s3-scope-review-evidence/` (about 1.37 MiB, tracked).
- Recommendation: A, an opt-in foreground daily brief, rather than recovery of
  the whole runtime. B adds at-due scheduling; C defers new behavior. Owner
  decisions remain: choose A/B/C and allow or refuse limited setup before phone
  delivery. Neither choice alone approves implementation.
- Accepted behavior comparison: `9e34df13e5b773ebf88032047fbe26a1088877bb`.
  Fresh source/report review `24ca43bd` and final-packet review `0d6e64d9`
  passed, both verified Luna/xhigh. The final closeout-only environment wording
  correction followed those reviews; Lead checked its exact diff, runner,
  config and symlink metadata. No secret value was read. Prior review receipts
  remain tied to their original exact refs, not the later wording.
- Fresh historical snapshot: 150 selected tests passed on exact `216b2eab`;
  not current compatibility or full S3 proof. Separately, actual combined-entry
  gates passed on their first runs: Python 1,792; frontend 1,115 each in UTC
  and Oslo; Ruff, ty, frontend lint/types/build. All 372 source/test/config
  hashes matched; Lead independently rechecked them and the unchanged report.
  No full browser rerun; task 1 remains partial/red. P2's flag remains false.
- Preservation: all 5,525 archive files (730,350,862 bytes), 36 exact resume
  refs, 60 source fingerprints, existing bookmarks, conflicts/divergence and
  other workspace targets matched. Only the report/evidence paths changed.
  Docs build exited 0 with 51 existing warnings; the excluded report had a
  separate source check of 48 targets, zero failures. Initial checker failures
  remain evidence, not passes.
- All four bounded runs finished. The owned historical snapshot, temporary
  data, copied dependencies and check panes 79/85/87/88 are removed. Entry and
  interactive peer remain for inspection. Graph coordination returned to Lead;
  no product work or archive cleanup is approved.

## Progress

- [x] Define the research-only assignment and link it from the backlog.
- [x] Approve execution limits.
- [x] Assign task ownership; record each child's ownership at launch.
- [x] Inspect relevant archived work and current-baseline compatibility.
- [x] Compare options and write the owner decision report.
- [x] Independently review the evidence, recommendation and final packet.
- [x] Deliver the report and recorded checks for the morning handoff.
- [x] Preserve evidence and remove owned snapshots, temporary data and jobs.
- [ ] Owner chooses scope and the limited-settings gate. No implementation is
  approved; keep this tracked plan for that decision.
- [ ] After inspection/acceptance, release the retained peer and remove the
  Lead-managed entry under the workspace policy.
