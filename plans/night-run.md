# Five-task overnight delivery

Lifecycle: temporary

## Approval and outcome

The owner approved execution in the Lead conversation on 2026-11-05. Work on
one task at a time. Follow the order below when possible. If a task is blocked,
preserve its result and blocker, then continue to the next task. This replaces
the earlier instruction to stop the whole run at a blocker.

The owner requested a stack of separate results, with a bookmark on each
finished step. This is permission to create the five result bookmarks below,
not permission to move existing feature, `integration`, or `main` bookmarks.
No push, deployment, automatic feature acceptance, S3 implementation, settings
reactivation, or S4/S5 restart is approved. Existing task exclusions still apply.

## Run limits and defaults

- Start: 2026-11-05 22:14 CET (21:14 UTC).
- Target: finish within about nine hours, by 2026-11-06 07:14 CET (06:14 UTC).
  Reserve time for independent review, combined checks, and the final report.
  Do not label partial work complete to meet the target.
- One active visible Conductor. At most two bounded workers/reviewers running
  at once across this delivery. Each concurrent writer has its own jj workspace.
- First worker/reviewer attempt: `openai/gpt-6-luna`, `xhigh`. After an
  unsatisfactory attempt, simplify the brief and use
  `claude-code/claude-haiku-5-5`, `max`, if quota is available. On a known
  Claude usage limit, use `openai/gpt-6.1-terra`, `low`. Verify every effective
  selection. Documentation writers/reviewers retain the owner's Luna/xhigh
  choice; escalate an incompatible fallback rather than silently substitute it.
- Retained generated evidence target: at most 3 GiB across the delivery. Keep
  failed evidence. Remove only confirmed disposable successful-run output.
  Pause new heavy jobs if free disk falls below 6 GiB; preserve results and
  report the resource blocker. Initial free space was about 16 GiB.
- No competing full-suite, browser, or profiling jobs. Bound browser traces.
  Use synthetic/disposable data. Do not read or print secrets.
- The existing docs preview on port 8765 remains owner-managed and running.
  A theme gallery may use a verified free loopback port in its own visible
  Zellij pane. Do not open a user browser tab.

These are Lead-selected operating defaults within the approved run, not new
standing project policy.

## Delivery line and ownership

- Repository and shared docs desk: `/home/hsa/projects/list_app`.
- Lead: session `01a1ad8b-c485-774e-bb47-66e425c18dc4`, effective
  `openai/gpt-6.1-sol`, `xhigh`; Zellij session `pc-home`, tab 1, pane 2.
- The Lead owns this record and the shared backlog. Task plans stay on the
  shared desk. Conductors request exclusive write windows for their task
  status/closeout; workers never edit the shared backlog or plans.
- The Lead creates each Conductor workspace, owns its lifecycle, and authorizes
  reviewed child integration into that task line. Each Conductor owns its
  workers and their workspaces. Keep successful peer conversations open.
- First task base: the accepted `integration` tip after this approval record.
  Each later task starts from the previous preserved result, including a
  clearly reported partial result if its task is blocked. Do not rebase earlier
  finished steps when preparing later ones.
- The final stack is for owner inspection, not accepted app/test code. Shared
  docs-desk approval records use the existing docs-only standing permission.
- Serialize all jj graph mutations across workspaces. The active Conductor
  coordinates its own workers. The Lead requests quiescence before shared
  docs commits, bookmark creation, workspace creation, or integration changes.
- Preserve `groups`, `reminders-s2`, parked conflicts/divergence, S3 recovery
  sources, archive records, and the two pre-existing temporary workspaces.

## Tasks and assignments

The linked briefs own scope and verification. The backlog owns priority and
Conductor selection. All five assignments are now approved within these limits.
Each is a large batch because it needs a coordinated inventory, specialist work,
and fresh independent review, even where the selected effort is low.

| Step | Brief | Conductor model/effort | Workspace | Finished bookmark |
| --- | --- | --- | --- | --- |
| 1 | [Test suite](test-suite-review.md) | Sol 6.1/high | `night-tests` | `night-1-tests` |
| 2 | [Documentation](documentation-ste100.md) | Sol 6.1/low | `night-docs` | `night-2-docs` |
| 3 | [Themes](theme-exploration.md) | Sol 6.1/low | `night-themes` | `night-3-themes` |
| 4 | [jj history](jj-history-review.md) | Sol 6.1/high | `night-history` | `night-4-history` |
| 5 | [S3 scope](reminders-s3-scope-review.md) | Sol 6.1/high | `night-s3-review` | `night-5-s3-review` |

Workspace folders are siblings named `list_app-<workspace>`. The Lead creates
them only when their task starts. Session/tab identities and exact bases are
recorded at dispatch. A blocked task gets a clearly labeled preserved result,
not a misleading finished bookmark. Resume blocked work if the blocker clears
and the remaining run permits it.

## Status

Approval recorded. No Conductor launched yet. Next: dispatch the test review.

## Closeout requirements

For each task, record completed/partial/blocked, exact result and bookmark,
checks and failures/skips, fresh-review disposition, preserved artifacts,
workspace/child disposition, and decisions needed with a recommendation.
Verify the combined stack, not only child reports. Keep unfinished task plans.
Retire this run plan only after its results, ownership, and follow-up work have
stable homes and incoming links are fixed.

## Progress

- [x] Record execution approval, operating defaults, stack destination, and limits.
- [ ] Finish or preserve task 1 with independent review and checks.
- [ ] Finish or preserve task 2 with independent review and checks.
- [ ] Finish or preserve task 3 with independent review and checks.
- [ ] Finish or preserve task 4 with independent review and checks.
- [ ] Finish or preserve task 5 with independent review and checks.
- [ ] Verify the combined stack, preserve evidence, and give the morning report.
- [ ] Complete safe cleanup and preserve any remaining ownership obligations.
