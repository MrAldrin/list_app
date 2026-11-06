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
- Result: `xqptskso` / `4a33175a`, bookmarked `night-4-history`; complete
  as a view-only report. Zero candidates qualified, so no history cleanup was
  performed. Report: `docs/background/jj-history-review.md`; tracked evidence
  directory: `docs/background/jj-history-review-evidence/` (about 1.7 MiB).
- Frozen entry: 969 visible commits, 28 heads, three conflicts, four divergent
  versions. All six empty anonymous leaves were workspace-held. All 36 archived
  exact resume commits remained readable: 26 change IDs visible, ten hidden-only.
  All 969 entry commits, 60 tree fingerprints, other workspace targets, and
  bookmarks were preserved; the archive checksum matched.
- Fresh Luna/xhigh review `9268096d` passed with one citation note, now fixed.
  It checked receipts, not live commands. The Lead reran the everyday/attention
  views and pinned full-history command. A Lead probe using `root` failed;
  the corrected `root()` probe passed. No application test claim is made.
- Final docs build exited 0 with 51 existing warnings; all 27 report source
  targets passed separate checks. Report-only source scope was checked by Lead.
- Both scouts and reviewer finished; no child workspaces. Owned check panes
  75/76 were closed. Under the owner's later cleanup instruction, Lead preserved
  the ignored post-commit receipt, closed pane 74/tab 23 and removed
  `night-history` and its folder. See the [cleanup record](night-run.md#retained-resources-and-next-decisions).
  All possible S3 sources remain protected; no historical cleanup was added.

## Owner follow-up: targeted cleanup

Lifecycle remains tracked. On 2026-11-06 the owner requested a new visible
Conductor to turn the view-only findings into a concrete cleanup discussion
and safe implementation. This is a new phase, not a claim that the original
inventory still describes the current graph.

### Outcome and limits

- Inspect the exact local `reminders-s2` and `groups` bookmarks; cached
  `usual-items-redesign@origin`, `wave2-bottom-bar@origin` and
  `integration@origin`; conflicted/divergent reminder lines; and loose
  unbookmarked heads. Distinguish accepted ancestry, equivalent implemented
  behavior, parked features, obsolete review leaves and unknown ownership.
- Produce `docs/background/jj-cleanup-review.md`: one-screen recommendation,
  exact before/after candidate table, recovery method, commands and approval
  boundaries. Aim for fewer useful working lines without losing recoverable
  source. A shorter log alone is not the requested physical cleanup proposal.
- The owner permits removal of the local `reminders-s2` bookmark if its exact
  tip is proved fully included in `main`, there is no active dependency on the
  bookmark name, its identity is recorded, and fresh review approves the action.
  Removing a bookmark is not deleting its commits. Keep its source recoverable.
- Treat origin references as separate local tracking and remote-server objects.
  Read-only remote inspection is allowed. Do not fetch while another graph
  window is active. No push or remote deletion until exact names and commands
  receive an explicit itemized owner decision. Do not delete local `integration`.
- Inspect `groups` before deciding whether to keep, retire or update it. A
  historical position alone does not justify rebasing. Do not move/rewrite its
  bookmark or original commits yet. An isolated exploratory copy may assess
  conflicts without changing the original; no product repair is approved.
- For reminder consolidation, compare exact divergent versions and descendant
  dependencies. Propose a durable, tested recovery archive before any hiding or
  abandonment. Do not assume Git objects or an old operation will survive GC.
  Preserve the external archive and every old exact source alternative until
  the owner approves the exact consolidation set. No bulk rebase/abandon, GC,
  artificial all-head merge, or silent conflict resolution.
- Preserve `main`, the five overnight result bookmarks, task 1's diagnostic,
  old temporary workspaces, retained `night-tests`, and the active runtime-docs
  task. Acceptance/deployment and feature completion are separate decisions.
- Implement only independently reviewed, explicitly permitted local cleanup
  after obtaining the graph window. Bring wider proposals to the owner first.
  Record operation IDs, recovery checks and every actual mutation.

### Assignment and coordination

- Large batch: history safety, exact recovery/version analysis, remote-reference
  semantics and owner decisions. Conductor `01a1afc6-f7c5-76e5-a8cf-9622e5f80bfe`,
  verified `openai/gpt-6.1-sol`, `high`; Zellij tab 18, pane 108
  (`list_app-jj-cleanup`). Lead report target:
  `01a1ad8b-c485-774e-bb47-66e425c18dc4`.
- Workspace: Lead-created/managed `jj-cleanup`, sibling
  `/home/hsa/projects/list_app-jj-cleanup`, from accepted `integration` after
  this assignment record. No `.env` is needed for history inspection; use the
  README's new-workspace setup before any separately approved app checks.
  Keep this new peer open while the owner discusses the cleanup;
  do not retain it automatically after completed work and owner handoff.
- Up to two bounded Luna/xhigh scouts/reviewers. Fresh actual-plan/command and
  post-action verification required. Use the role retry policy on failed work.
- Runtime documentation owns docs/nav in `test-runtime-docs`. The cleanup peer
  may inspect read-only while that task owns the exclusive graph window. It
  must obtain an explicit handoff before any jj mutation, child workspace,
  fetch, bookmark change or report commit. Shared backlog/plans stay Lead-owned.
- No new app/server work. Use fixture data if a bounded isolated compatibility
  check is later justified. Do not load production/private setup for history
  inspection. Existing docs preview pane 38/8765 remains untouched.

### Follow-up result and pending decisions

Reviewed report tip: `vuvzlzuy` /
`62b9a607c506cc39b394ff9a373ddcdb48c49477`. Prior reports `abb53d81`,
`629e8884`, `325a8384` and `dc6d14e6` remain unchanged ancestors.
Read `docs/background/jj-cleanup-review.md` at that revision; it is not yet
accepted into the default workspace. The entry remains for owner discussion.

- Performed: local `reminders-s2` bookmark forget; exact source `e50da7ce`
  remains in main. The owner then explicitly approved execution of set A.
- Set A completed: 11 exact empty checkpoints retired in ten operations;
  heads fell from 28 to 18. Immediate visible inventory fell from 992 to 981.
  Every operation passed full retained Git-object/tree, native jj metadata,
  reference, workspace, config and recovery checks. All 67 protected trees,
  including 36 archived resume sources, matched. Retired source remains
  readable and archive-matched. A left three conflicts/four divergent versions.
- The owner then approved and executed set B: exact unused alternatives
  `d8e8f994` and `31077a91` retired in two singleton operations. Heads fell
  from 18 to 16, conflicts from three to two, divergent versions from four to
  zero. This is archival retirement, not merging or repairing code. Only the
  exact retained siblings' divergence flags changed; full retained Git/native
  checks and 79 protected trees passed. Both retired sources are recoverable.
- Pending owner decisions: two exact obsolete origin feature names and report
  integration. No remote, GC, product or additional bookmark action occurred.
- Keep original `groups` and `integration@origin`. Groups has real unfinished
  work and migration-number collisions; a later port needs its own approval.
- Private native recovery is retained at
  `/home/hsa/projects/list_app-jj-recovery-20261106-01a1afc6/`. The Conductor
  tested isolated restore; independent reviewers checked receipts, not a fresh
  native rerun. Original blocked review, config-ID side effect, exact approved
  repair, wrapper timeout and later successful validation remain recorded.
- Earlier static report/receipt reviews passed. Set A's initial Luna guard
  review blocked incomplete metadata claims; the guard was strengthened, then
  Haiku/max pre-action reviews passed. The post-action Luna review lacked
  Python capability and blocked without finding a repository failure.
  Owner-selected Terra 6.1/medium independently ran a static Python audit:
  43 hashes, ten full maps, 9,864 retained entries and 130 protected fields
  passed. This is receipt verification, not a fresh native execution.
- B's independent Luna/xhigh Python preflight passed. Haiku/xhigh independently
  checked 20 hashes, two full maps, exact flags, trees and descendants, but its
  raw verdict blocked historical/live head provenance. A correction attempt
  stopped on a Python schema error. Lead independently executed the six-file
  static correction and passed both projections plus the two documented cursor
  replacements. Both BLOCKs remain; this is not an independent native rerun.
- No app tests were needed or claimed. Conservative evidence use is
  2,841,321,472 bytes, below 3 GiB; free disk remained above 6 GiB.
- Transient recovery copies and owned scratch files are removed. Durable
  archive/receipts and Lead-created entry remain. No children/jobs are active.
  Graph released to Lead after set B closeout; further work needs an explicit
  window. Report integration and remote actions are not approved.
  Private raw receipts/methods are under the recovery directory's
  `set-a-20261106/` and `set-b-20261106/`; report indices record hashes/paths.

### Owner closeout

The owner closed this batch and requested another jj history review in Later.
No further cleanup or remote action is authorized. The Conductor released all
ownership; its pane 108 is closed, with no owned job or child remaining.
An additional user/unknown-owned shell pane 110 still has the entry as cwd.
Do not close it or remove the workspace/folder without owner approval; that
last resource cleanup is pending. Retained `night-tests`, old workspaces and
the docs preview remain untouched.

The exact report chain is also preserved outside the entry in the private
recovery directory's `completed-report.bundle` (3,116,093 bytes), SHA-256
`052cb8e67e3b5d03572e53da1ed95668d7085ae46478276ae65127b88ebb3364`.
Lead imported it into a separate empty bare Git repository and verified full
ancestry, five exact report commit bodies/trees and all 62 report/evidence
entries. Temporary export/import repositories were removed. This is backup
verification, not acceptance of the report into `integration`, nor a new native
jj restore. `completed-report-bundle.json` holds the receipt. Keep the original
native tar, private A/B receipts and harness artifacts too.

## Progress

- [x] Define review outputs, bounded cleanup, and explicit approval gates.
- [x] Approve execution limits.
- [x] Establish ownership and coordination windows.
- [x] Inventory the current graph, ownership, and recovery dependencies.
- [x] Prepare readable log views and classify cleanup candidates.
- [x] Establish that no Bucket A cleanup qualifies; independently review results.
- [x] Deliver the report and Bucket B proposal list; no broader action approved.
- [x] Preserve evidence and remove owned check panes; no child workspaces.
- [x] Preserve the ignored closeout receipt and remove the entry/session under
  the owner's later cleanup approval, without accepting the task line.
- [x] Owner reviewed the view-only outcome and requested the targeted follow-up.
- [x] Assign/verify cleanup Conductor; initially read-only during runtime-docs
  graph ownership. Obtain explicit graph handoff before mutation.
- [x] Refresh exact candidates and ownership; propose reviewed cleanup/recovery.
- [x] Obtain explicit set A execution permission; retire only the 11 selected
  empty checkpoints and independently audit the actual operation receipts.
- [x] Obtain explicit set B execution permission; retire only the two selected
  alternatives, verify native retained state and independently audit receipts.
- [x] Complete only approved local actions; owner closed this batch and moved
  another review and remaining decisions to Later. No wider permission carries.
- [ ] Verify retained source, archive and references; record resource cleanup.
