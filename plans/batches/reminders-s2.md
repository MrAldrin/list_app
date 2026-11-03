# Reminders S2: Personal policies, dates and previews

Lifecycle: tracked

## Brief — frozen at handoff

**Outcome/scope:** Implement approved stage 2: installation/enrollment identity and private APIs, device/room/list/item policy inheritance, presets and five effective relative/fixed reminder rules, optional shared due time/zone with canonical server due_at, one resolver/preview and complete offline/undo/feed compatibility. No real scheduling or push sends yet.

**Edit seams:** src/reminders, src/api/reminders and existing item ops/CRUD/migrations/feed; frontend types/validation/offline overlays, reusable reminder editor/settings and previews. Keep personal data out of shared feeds and share-link APIs.

**Dependencies:** Stage 1 reviewed and integrated into the Lead line; exact base supplied at dispatch.
**Unblocks:** [S3](reminders-s3.md).

**Done criteria:** Users can explicitly enroll this installation, save understandable policies/overrides and inspect next-run previews; invalid ownership/rules/timezones fail safely. Time changes use the established shared mutation and offline conflict/restore rules. Phase-2 UI clearly says delivery is not active yet.

**Verification:** Full Python gates, frontend gates, full three-engine browser suite. Include DB upgrade, cookies/auth/privacy, idempotency/revision conflicts, absent/null/legacy op hashing, DST gap/fold/calendar boundaries, fixed-vs-relative and image tzdata availability. Full commands live in the master plan's
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
- Planned owner: dedicated visible Pi Conductor `listr-reminders-s2`.
- Model: `openai-codex/gpt-6.1-sol:high`; effective setting to be verified before edits.
- Repository: `/home/hsa/projects/list_app`.
- Lead aggregate: `tmp-reminder-delivery`, `/home/hsa/projects/tmp-reminder-delivery`.
- Entry workspace: `tmp-reminders-s2`, `/home/hsa/projects/tmp-reminders-s2`;
  Lead-created/agent-managed; creation and exact base pending dispatch.
- Exact peer identity, Zellij location and base change: pending readiness.
- Child fanout: workers and independent review authorized within this brief;
  isolated concurrent editors, no unrestricted recursive delegation.

## Status — assigned Conductor writes after handoff

- State: blocked by predecessor stage.
- Next: Lead creates workspace and verifies the dedicated peer, then hands over.
- Children/workspaces: none yet.
- Docs-desk status write ownership: Lead until edit handoff; Conductor thereafter.

## Closeout — assigned Conductor

- Result/change IDs: pending.
- Independent review and checks: pending.
- Assumptions, limits and retained artifacts: pending.
- Child cleanup/entry cwd release: pending.
- Owner review/acceptance: pending; no deployment.
