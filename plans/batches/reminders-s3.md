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

**Successor (2026-11-05):** Lead Pi `01a1aa7e`. The original S3 Conductor
session was closed at owner request. New Conductor `reminders-s3-list-app`
(GPT-6.1 Sol/medium) takes over ownership of all `tmp-reminders-s3*`
workspaces and the runtime records in
`/home/hsa/projects/tmp-reminders-s3/.pi/reminders-s3-runtime/`. Start from the
latest final disposition in its `DEADLINE-0410.md`/`CURRENT.md`. Details below
are historical.

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

- **Full S3 unfinished.** No complete local app, full-stage acceptance or
  deployment. No unreviewed S3 source was merged into Lead's aggregate.
- Reviewed-component tree `kulntpxm/4ffec984`; own combined working child
  `smxxkylq/83609b2af045` has identical source. All six Python gates passed:
  **2,254 tests, zero skips**, format/Ruff/ty clean. Frontend is unchanged
  from the earlier 1,155-test validated build; not the pending strip UI.
- Final unreviewed candidates: item API `yoounzxz/3f620969` needs fresh
  same-626 review; strip UI `syollnqp/38eea306` needs fresh same-204 review.
  Neither was accepted or consumed into the combined root.
- Still required: complete causal/grouped cap B26, actual repeat27,
  cooldown A28, known-absence fallback, summary/manual29 and remaining UI,
  then latest full combined browser and independent full-stage gates.
- Entry remains `wnyyylyt/54561d1c`. No main/integration/other bookmark,
  production or provider changes. Implementation and review children used
  verified native Terra/medium; no further reviews or source work in this window.

## Closeout — assigned Conductor

- Window ended with all child jobs complete and no owned test/preview server
  remaining. No complete morning preview was started. All 16 extant S3
  directories and partial changes are retained; no destructive cleanup.
- Definitive root/gates, exact partial sources, missing behavior and next
  executable steps are retained under
  `/home/hsa/projects/tmp-reminders-s3/.pi/reminders-s3-runtime/`:
  `DEADLINE-0410.md` and `CURRENT.md`. Native reports remain outside
  `/tmp`; copied logs/probes have a SHA256/source manifest.
- Evidence gap: an earlier failed WebKit matrix's textual log is retained,
  but its trace was lost to pytest temporary retention. Later focused green
  results are not a full-browser gate or proof of the earlier error's cause.
- Next session: independently review exact `3f620969` and `38eea306`,
  including the stronger privacy/group proofs and UI test adjustment.
  Join only approved sources, rerun applicable gates, then complete the
  missing scope. No fake acceptance or automatic integration.
