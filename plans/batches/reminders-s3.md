# Reminders S3: Durable in-app reminders and snooze

Lifecycle: tracked

## Brief — frozen at handoff

**Outcome/scope:** Implement stage 3 in internal 3a/3b/3c steps from the plan: persistent occurrence/outbox/watermark/leases and saved-grant cancellation; protected daily summaries/history/strip; scheduled/fixed rules, snooze/dismiss/off, quiet hours, caps/spacing, repeats, pruning and recovery. No real phone push.

**Edit seams:** Existing approved reminder models/evaluator/API; server lifespan supervised task and bounded DB/I/O separation; private inbox/settings/action UI. Reuse one evaluator/outbox. Never hold DB transactions across network or expose an unprotected partial dispatcher.

**Runtime dependencies:** Reviewed full S2 before evaluator/scheduler/API/UI
integration. Lead sequencing handoff (2026-11-04) permits an independent durable
storage foundation now from reviewed identity/cycle tip `rwswntvl` / `3eb72704`.

**Foundation edit handoff:** Conductor creates/owns
`tmp-reminders-s3-store` from that completed tip, not the provisional entry.
Implement real SQLite occurrence/outbox/watermark/lease/reservation persistence
and atomic repository operations/tests against the existing identity/grant
helpers. Use the master record/state/retention contracts; agree concrete seams
directly with S2/S4/S5. No invented policy/evaluator stubs, generation loop,
lifespan task, dispatch, API/UI or shared migration-runner edits yet. Keep DDL
in this module for direct repository tests; register its migration after S2
schema integration. Fresh independent review/full Python gates are required.
Integrate the reviewed foundation into the released empty S3 entry only; full
stage/aggregate integration still waits for the reviewed predecessors.
**Unblocks:** [S4](reminders-s4.md).

**Done criteria:** Configurable in-app reminders, safe dedupe, one tab-claimed strip, snoozes and history survive reload/restarts. No navigation spam or cross-installation action effects. Cancellation/revocation, future-only setup and finite catch-up are explicit and tested.

**Verification:** Full Python/frontend/browser gates plus deterministic fake-clock/fake-sender tests for restarts/leases, watermark/prune replay, multiple tabs/rooms, grouped bursts, quiet hours/DST, same-/cross-day retry quotas, fixed-rule identity, snooze coalescing and completion/reset/logout/deletion. Serverless-off is a future rollout precondition, not an instruction to change Railway now. Full commands live in the master plan's
verification section and AGENTS.md. Keep tests with their behavior; re-review
material fixes after independent review.

## Authority and operating rules

- Owner selected A/A/A and explicitly approved all five stages on 2026-11-03.
  Read the [master plan](../due-date-reminders.md) in full and follow its product contract.
- Read `/home/hsa/projects/my_personal_skills/skills/conductor/SKILL.md` and its
  required `../lead/workflow.md` in full before execution. Stay in the Conductor role.
- Use bounded workers for all implementation and fresh independent reviewers.
  Follow the current model/provider exception in the
  [master delivery contract](../due-date-reminders.md#delivery-coordination);
  verify effective model/effort and report unsupported settings.
  You may create isolated jj child workspaces and integrate reviewed children
  into your assigned stage workspace without repeated approval.
- Lead owns your entry workspace lifecycle; you own your child workspaces.
  No parallel writers in a workspace. Do not delete your entry workspace.
- No changes to `main`, feature acceptance via `integration`, pushes, deployment,
  production configuration, real notification enrollment/sends, paid service or
  budget increases. Parked `groups` and unrelated work stay untouched.
- Routine implementation assumptions are delegated; record a short TLDR.
  Escalate only a material security/scope/authority/environment blocker to Lead,
  with evidence and a recommendation. Never silently reduce approved behavior.
- Source/test/current-behavior docs changes stay in your isolated stage line.
  Never edit the backlog or the master plan from a feature workspace.
- Your batch status/closeout is yours alone, in this file's authoritative copy
  under `/home/hsa/projects/list_app/plans/batches/`. Request a short docs-desk
  write window from Lead, then edit/commit only this file there and release it.
  Do not run simultaneous jj mutations in the shared docs desk. Do not move
  bookmarks yourself; send Lead the record-only commit ID so Lead can advance
  the docs baseline under its standing permission. Do not edit a divergent
  copy of this record in your stage workspace. Lead owns brief
  changes; ask before changing the frozen brief.
- Read scope/architecture/current instructions. New workspaces need the README
  setup; symlink the existing .env when needed, never print secrets or share DBs.
  Use disposable test databases, fake sender/clock and no real external sends.
- Report via intercom to Lead session
  `01a1a2c7-22c9-71e2-897a-af8ac7de162d` in the coordination workspace.
  Readiness must give exact session ID, cwd, effective provider/model/thinking
  and Zellij session/tab/pane. Await the edit handoff after two-way readiness.

## Assignment

- Creator/lifecycle owner: Lead, session `01a1a2c7-22c9-71e2`.
- Planned owner: dedicated visible Pi Conductor `listr-reminders-s3`.
- Verified model: `openai-codex/gpt-6.1-sol`, effective thinking `high`;
  peer environment matches the explicit launch setting.
- Repository: `/home/hsa/projects/list_app`.
- Lead aggregate: `tmp-reminder-delivery`, `/home/hsa/projects/tmp-reminder-delivery`.
- Entry workspace: `tmp-reminders-s3`, `/home/hsa/projects/tmp-reminders-s3`;
  Lead-created/agent-managed; initial preflight @ `wnyyylyt`, base
  `rptqkywz` / `72b25032`. Lead will supply the reviewed predecessor tip
  before implementation; do not implement on this provisional base.
- Peer: `01a1a2ff-4f0f-707a-a745-48b66ff3a604`.
  Zellij `pc-home`, tab 12 **ListR S3 reminder engine**, pane `terminal_21`.
  Normal Fish shell, target cwd and foreground Pi launch verified.
- Child fanout: workers and independent review authorized within this brief;
  isolated concurrent editors, no unrestricted recursive delegation.

## Status — assigned Conductor writes after handoff

- State: independent storage foundation reviewed, verified and integrated into
  own S3 entry only. Full 3a evaluator, 3b/3c and aggregate integration remain
  pending reviewed full S2 plus exact Lead runtime EDIT HANDOFF.
- Result tip `ozymolps` / `3e83454d`, based on reviewed identity/cycle
  `rwswntvl` / `3eb72704`; entry clean `wnyyylyt` / `38322846` above it.
  Local DDL is unregistered. No scheduler, dispatch, API or UI is enabled.
- Implemented repository: occurrence/immutable-group/outbox persistence,
  atomic processed-through cursor and retained dedupe, fenced leases and
  per-generation attempt/member ledger, device-global quota/spacing,
  scoped lifecycle cancellation/recovery/pruning and external-cutoff input.
- Owner model change applied: Sol worker checkpointed/stopped; implementation
  and independent executable reviews used native `openai/gpt-6.1-terra`,
  medium, with effective settings verified. Conductor remains Sol/high.
- Direct dependencies: S2 reviewed policies `qpwvmpyv` / `3c265a95` and
  preview `xtmnuruo` / `98c37a22` are reported ready server-side; full S2 UI
  is still active. No unfinished source consumed. Reconcile optional grant
  clock helper and register local DDL only on the actual reviewed S2 handoff.
- Binding grouping clarification: atomically reject future scheduled/eligible/
  wake instants. Future fixed work stays ungrouped; accepted groups never
  reopen. Negative premature-group, stable fixed reactivation, mixed-member
  cancellation and accepted-history regressions pass.
- Future caller obligations: couple item mutation and `cancel_item_locked` in
  one transaction; commit and use only `mark_attempt_locked`'s exact member
  snapshot before I/O. Live started claims retain leases through result or
  recovery. Acceptance is not display; no network under the DB lock.
- S4 uses the same stable group/topic, attempt ledger and reservations; no
  uncertainty fallback strip. S5 supplies the external cutoff: strict actual
  eligible/wake comparison retains equality/future work and attempted charges.
  Runtime status enums, diagnostics and transport bridge remain unimplemented.
- Children: `tmp-reminders-s3-store` created/owned by this Conductor, reviewed
  work preserved in entry; forgotten and folder removed after no-process,
  reachability, clean-state and ignored-artifact checks. No live children.
- Entry remains interactive and Lead-managed. Shared-desk Status/Closeout
  updates require coordinated windows; Brief/Assignment stay Lead-owned.

## Closeout — assigned Conductor

- Partial result stack: `oprzrxlr` / `861a6faf` (repository/tests),
  `nzzozpnt` / `d85897d4` (member lifecycle/late acceptance),
  `ozymolps` / `3e83454d` (live leases and cancellation reservations).
  Four-file foundation delta; not full S3 completion or feature acceptance.
- Independent Terra/medium full shell review `33846137` blocked two executed
  cancellation defects; material re-review `84733408` approved after fixes.
  Exact retained reports:
  - `/home/hsa/.pi/agent/sessions/--home-hsa-projects-tmp-reminders-s3--/subagent-artifacts/outputs/33846137-5794-45fd-893c-e6ddcc9867c6/s3-store-final-review.md`
  - `/home/hsa/.pi/agent/sessions/--home-hsa-projects-tmp-reminders-s3--/subagent-artifacts/outputs/33846137-5794-45fd-893c-e6ddcc9867c6/s3-store-final-review.84733408.md`
- Final author and independent review: 33 targeted repository tests pass;
  full Python suite 1,721 passed/nine skipped, Ruff format/lint and ty clean.
  Own-entry integration reran all six Python gates successfully (54.91-second
  pytest), zero working-copy diff. Missing frontend-build warning retained;
  frontend/browser gates do not apply to this inactive backend-only lane.
- Retained local evidence: entry `.pi/reminders-s3-store/ownership.md`,
  `checks/integrated-pytest.log`, and `child-artifacts/` checkpoints/historical
  repro scripts; native worker/review reports remain outside the deleted child.
  Copied artifacts checked equal; scripts parse without child-path imports.
  Old defect repros are historical evidence, not current passing test cases.
- Explicit conservative limit: cancellation after an earlier-day attempt also
  retains a later-day unattempted reservation. No attempted/ambiguous refund
  or spacing rewind is claimed. Started I/O cannot be recalled; lease-expiry
  retry can still be ambiguous. No real transport or services were run.
- Next: reviewed full S2/runtime handoff, schema/helper reconciliation, then
  actual evaluator/lifespan/protected in-app scheduling and full-stage gates.
  No fake evaluator adapters, shared migration changes, main/integration moves,
  deployment, production configuration or real notification enrollment.
- Child cleanup complete; entry stays available. Owner acceptance/deploy pending.
