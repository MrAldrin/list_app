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
- Task owner/session, effective model/thinking verification, and workspace: pending.
- Work window, concurrency, and artifact budget: [overnight run limits](night-run.md#run-limits-and-defaults).
- Browser/check schedule with other tasks: not agreed.

## Progress

- [x] Define the research-only assignment and link it from the backlog.
- [x] Approve execution limits.
- [ ] Assign task and child ownership.
- [ ] Inspect relevant archived work and current-baseline compatibility.
- [ ] Compare options and write the owner decision report.
- [ ] Independently review the evidence and recommendation.
- [ ] Deliver the morning handoff; await the owner's scope decision.
- [ ] Preserve evidence, record follow-up work, and clean up owned workspaces.
