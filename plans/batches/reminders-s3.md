# Reminders S3: Durable in-app reminders and snooze

Lifecycle: tracked

## Brief — frozen at handoff

**Outcome/scope:** Implement stage 3 in internal 3a/3b/3c steps from the plan: persistent occurrence/outbox/watermark/leases and saved-grant cancellation; protected daily summaries/history/strip; scheduled/fixed rules, snooze/dismiss/off, quiet hours, caps/spacing, repeats, pruning and recovery. No real phone push.

**Edit seams:** Existing approved reminder models/evaluator/API; server lifespan supervised task and bounded DB/I/O separation; private inbox/settings/action UI. Reuse one evaluator/outbox. Never hold DB transactions across network or expose an unprotected partial dispatcher.

**Dependencies:** Stage 2 reviewed and integrated into the Lead line; exact base supplied at dispatch.
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
  Subagents: explicitly select Claude Haiku 5.5/medium first, Haiku 5.5/max on
  escalation; verify effective model/effort and report unsupported levels.
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

- State: blocked by predecessor stage.
- Next: complete two-way readiness and read-only preflight; wait for reviewed
  predecessor integration and explicit Lead edit handoff before implementing.
- Children/workspaces: none yet.
- Docs-desk status write ownership: Lead until edit handoff; Conductor thereafter.

## Closeout — assigned Conductor

- Result/change IDs: pending.
- Independent review and checks: pending.
- Assumptions, limits and retained artifacts: pending.
- Child cleanup/entry cwd release: pending.
- Owner review/acceptance: pending; no deployment.
