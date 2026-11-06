# Review and simplify the jj history

Lifecycle: tracked

## Status and outcome

The owner approved this review and bounded-cleanup assignment within the
[overnight run limits](night-run.md). The result must explain the history and
propose cleanup. Only the narrow Bucket A actions below are permitted; execution
approval does not authorize broader graph edits.

Make it easy for a person to distinguish accepted work, active work, parked
experiments, and disposable leftovers. Preserve code, recovery points, evidence,
and other agents' ownership. Do not force a straight line just for appearance.

The [backlog](backlog.md#next) owns priority. Repository instructions and
[scope gates](../docs/scope.md#gates) remain in force. In particular, this task
is not approval to rewrite shared feature history or move bookmarks.

## Initial evidence — refresh at execution

A read-only snapshot taken while drafting this plan found:

- 186 visible commits outside the ancestry of `main`.
- 64 undescribed commits and 42 empty commits within that set.
- Four divergent commit versions (two change IDs) and three conflicted commits.
- Workspaces: `default`, `tmp-fix-queue-date`, and `tmp-reminder-delivery`.

These are diagnostic counts, not a deletion list. They can change before the
run. The full graph must be inspected again before any recommendation or action.

Empty working-copy children are normal in jj. An empty merge can join histories
without adding a separate diff. Empty changes may also be meaningful checkpoints.
A missing description is a readability problem, not proof of missing code or
repository corruption. Divergence means multiple versions of the same change;
it is not the same as two unrelated feature lines.

## Investigation

1. Read `AGENTS.md`, scope, the jj workflow skill, and workspace-ownership rules.
   Inspect status, bookmarks, workspaces, graph, and recent operations. Preserve
   the current workspace and any uncommitted edits.
2. Establish the actual accepted and production ancestry. Identify active peer
   sessions and their workspaces before treating anything as abandoned.
3. Inventory unbookmarked heads, anonymous changes, empty changes/merges,
   divergent versions, conflicts, stale workspace heads, and local/remote
   bookmark differences. Inspect diffs and parents, not just descriptions.
4. Classify each candidate: accepted history, active work, parked recoverable
   work, reviewed checkpoint, disposable leftover, or unresolved ownership.
5. Establish why the graph looks complex. Separate clutter from genuine
   conflicts, incompatible duplicate versions, or unsafe baseline relationships.
6. Propose a short everyday log view and a separate full/recovery view. Verify
   commands against the installed jj version. Do not hide conflicts and then
   claim that they were fixed.

Use a table with exact change IDs and full commit IDs where needed:

| Candidate | Role/owner | Content and ancestry | Recovery/evidence references | Proposed action | Approval needed |
| --- | --- | --- | --- | --- | --- |

For each divergent change, inspect the exact commit versions. A short change ID
alone is ambiguous. Identify which differences are meaningful and which version,
if any, has independent review or verification. Do not choose a version based
only on recency or apparent neatness.

## Coordinate with S3 recovery and other overnight work

The [S3 scope/recovery review](reminders-s3-scope-review.md) needs parked source
and exact references. Read its ownership and current status. Do not alter any
candidate it depends on before it has finished identifying the sources to retain.
The archive's older IDs may have changed after rebases; resolve references from
current history rather than assuming the archive is complete.

Read-only graph review may run alongside other work. Mutations require an
exclusive coordination window: tell active agents what is changing, confirm
quiescence where relevant, then recheck status and operations immediately before
acting. A shared jj repository means separate workspaces do not isolate graph
mutations.

Do not rebase another agent's work, update another workspace's revision, or clean
up its directories because its pane appears idle. Unknown ownership means stop
and report the candidate, not infer permission.

## Bucket A — bounded cleanup allowed during an approved run

The owner allows obvious cleanup within this narrow boundary. Every action must
be recorded with before/after references and a tested or credible recovery path.
If any condition is uncertain, move the candidate to Bucket B.

- Remove temporary workspaces and scratch artifacts created by this review,
  after checks/runs stop and all results are preserved. Use native workspace
  forgetting before removing the owned directory.
- Abandon an empty, undescribed disposable leaf only if **all** of these hold:
  - It has no descendants, conflict, or divergent version.
  - No bookmark or workspace points to it, and it is outside protected accepted
    history and all active work.
  - Ownership is established, the work is inactive, and its owner has released
    it for cleanup. Do not treat absence of a live session as a release.
  - It is not a merge, named checkpoint, review tip, archive resume point, or
    source needed by the S3 review or another handoff.
  - Inspecting its tree confirms it adds no content. Abandoning it changes no
    protected source tree or unrelated revision.
  - Record its full IDs and the pre-action operation ID outside disposable
    storage before abandoning it.
- Add a factual description to an undescribed change created by this review.
  Renaming historical changes is a proposal unless separately approved.

Use exact individually checked IDs, one bounded set at a time. Never run broad
commands such as abandoning every `empty()` or `description(exact:"")` match.
Do not garbage-collect recoverable history. Operation undo is a safeguard, not
permission to take speculative actions; it can also affect concurrent work.

## Bucket B — recommendations only

Ask before:

- Abandoning any change with content, any meaningful checkpoint, or a merge.
- Resolving divergence by discarding one version, or resolving conflicts.
- Rebasing, squashing, splitting, merging, or rewriting existing feature or
  accepted history, including adding descriptions that rewrite descendants.
- Moving, deleting, or creating bookmarks, including stale remote references.
- Removing workspaces that existed before this review or were created by others,
  unless explicit ownership and cleanup authority are transferred.
- Changing the user's default jj configuration, aliases, immutable-history
  policy, or log template. Provide verified suggested commands first.
- Rewriting archive references or removing retained failed-test evidence.

For each recommendation state the readability benefit, code/recovery risk,
exact affected revisions, expected descendant effects, and smallest safe action.
Offer a view-only option where physical history cleanup has little benefit.

## Suggested result structure

Write `docs/background/jj-history-review.md` with a one-screen owner summary:

1. What makes the graph confusing and what, if anything, is genuinely wrong.
2. Which obvious cleanup was performed, with exact references and reasons.
3. Verified everyday and full-history commands, with a plain explanation.
4. A short approval list for broader cleanup, ordered by benefit and risk.
5. Remaining conflicts/divergence, recoverable work, and ownership gaps.

Keep the full inventory, before/after graph snapshots, command results, and
recovery references below the summary. Do not copy the whole raw log into the
backlog. Update workflow documentation only for owner-accepted lasting rules;
proposed workflow changes stay labeled as proposals.

## Checks and morning handoff

Before and after any permitted mutation:

- Record operation ID, status, bookmarks, workspaces, candidate IDs, and graph.
- Confirm `main`, `integration`, `groups`, other feature bookmarks, and active
  workspace revisions were not changed by cleanup.
- Verify protected source trees are identical and retained work is reachable.
- Recount conflicts/divergence and investigate any new ones immediately. Stop
  rather than continuing a cascade. Coordinate any rollback with active agents.
- Validate documentation links for report/guide edits. No application test suite
  is required merely for view-only review or abandoning a proven empty leaf.

A fresh reviewer checks the classification, safe-cleanup conditions, retained
recovery references, and proposed commands. The handoff includes the report,
checks, exact actions, unresolved approvals, task change IDs, and workspace/agent
cleanup state. Say clearly whether the graph was changed or only a clearer view
was prepared. Do not claim a tidy view means the entire history is resolved.

## Execution record

- Priority, difficulty, and selected Conductor: see the [backlog](backlog.md#next).
- Execution approval: [overnight run](night-run.md#approval-and-outcome).
- Conductor: `01a1ae6e-7f90-737d-9641-3e0947c7cfc9`, verified
  `openai/gpt-6.1-sol`, `high`; Zellij tab 23, pane 74 (`list_app-night-history`).
- Large batch: graph/ownership inventory, safe-history classification, recovery
  protection, readable views, and fresh independent review.
- Workspace: `night-history`, `/home/hsa/projects/list_app-night-history`;
  Lead-created and managed. Base: `night-3-themes` (`yuqlozro` / `44686493`).
  Lead owns entry lifecycle; Conductor owns children. Lead report target:
  `01a1ad8b-c485-774e-bb47-66e425c18dc4`.
- Work window, concurrency, and artifact budget: [overnight run limits](night-run.md#run-limits-and-defaults).
- Conductor receives the exclusive graph window at dispatch; earlier tasks
  are quiescent. Shared plans/backlog remain desk-owned. All parked S3 sources,
  archive/review checkpoints, and task 1 diagnostic must remain unchanged.
  The S3 recovery review follows this task; do not mutate its possible sources.
- Bucket A authority: scoped above; no broader graph rewrite approved.

## Progress

- [x] Define review outputs, bounded cleanup, and explicit approval gates.
- [x] Approve execution limits.
- [x] Establish ownership and coordination windows.
- [ ] Inventory the current graph, ownership, and recovery dependencies.
- [ ] Prepare readable log views and classify cleanup candidates.
- [ ] Perform eligible Bucket A cleanup; independently review results.
- [ ] Deliver the report and Bucket B approval list.
- [ ] Preserve evidence and remove this review's own temporary resources.
