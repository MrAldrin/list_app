# Reminders S5: Finish and owner review package

Lifecycle: tracked

## Brief — frozen at handoff

**Outcome/scope:** Implement stage 5: finish mobile/accessibility/settings polish, safe diagnostics/operational switches and restore behavior, current docs consistency, complete checks and a concise owner-review package with assumptions/limits. Delegate all code fixes to bounded workers. No deployment or main/integration feature acceptance.

**Edit seams:** Only integration issues and missing approved behavior across existing reminder code/tests/docs; no new product features. Current behavior docs/ARCHITECTURE should already be updated by stages; verify completeness. Prepare a useful local preview using existing helpers if safe, without touching production data or taking port 8080 from another process.

**Dependencies:** Stage 4 reviewed and integrated into the Lead line; exact base supplied at dispatch.
**Unblocks:** Owner review; acceptance/deployment are separate.

**Done criteria:** All approved stages work together; no blocking findings after fresh independent final review. Complete automated evidence, honest physical push limits and a TLDR of implementation assumptions are ready. Provide a stable completed change ID and preserve any needed artifacts. Leave acceptance/deploy to owner.

**Verification:** Run all Python gates, frontend format/lint/check/unit/build, full Chromium/Firefox/WebKit suite (-n 4), and relevant existing Android emulator suite if available. Do not install an emulator or accept SDK terms without approval. A missing environment capability is a reported limit, not a fake pass. Fresh end-to-end review must be independent of implementers. Full commands live in the master plan's
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
- Planned owner: dedicated visible Pi Conductor `listr-reminders-s5`.
- Verified model: `openai-codex/gpt-6.1-sol`, effective thinking `low`;
  peer environment matches the explicit launch setting.
- Repository: `/home/hsa/projects/list_app`.
- Lead aggregate: `tmp-reminder-delivery`, `/home/hsa/projects/tmp-reminder-delivery`.
- Entry workspace: `tmp-reminders-s5`, `/home/hsa/projects/tmp-reminders-s5`;
  Lead-created/agent-managed; initial preflight @ `pysuorwt`, base
  `rptqkywz` / `72b25032`. Lead will supply the reviewed predecessor tip
  before implementation; do not implement on this provisional base.
- Peer: `01a1a2ff-5049-7736-b625-bfea37e24b4c`.
  Zellij `pc-home`, tab 14 **ListR S5 finish and review**, pane `terminal_23`.
  Normal Fish shell, target cwd and foreground Pi launch verified.
- Child fanout: workers and independent review authorized within this brief;
  isolated concurrent editors, no unrestricted recursive delegation.

## Status — assigned Conductor writes after handoff

- State: quiescent, blocked by reviewed predecessor integration. Two-way
  readiness and read-only preflight accepted by Lead.
- Next: await exact reviewed S4 base, coordinated entry rebase and explicit
  edit handoff. No implementation, children or services started.
- Proposed bounded work: integrated-contract gap review; isolated backend
  diagnostics/restore and frontend mobile/accessibility fixes; docs/evidence
  consistency; fresh independent final review and complete combined checks.
- Interface needs: S3 scheduler status, switches, cursor/outbox and claim
  semantics; S4 safe configuration-health/fallback states; S2 revision,
  inheritance and preview contracts; S1 dialog/focus/theme conventions.
  Re-inspect implemented interfaces after handoff; provisional legacy source
  observations are not predecessor findings.
- Accepted safety direction: keep public `/healthz` DB-only. Expose safe reason
  enums, last tick and own queue state only through own-device/room-authorized
  reminder settings/status; no global private history or new admin access model.
- Restore: use an explicit external resume cutoff that survives DB replacement;
  suppress work whose actual eligible/wake instant precedes it, retain legitimate
  future work, and verify against S3 storage with fake-clock tests. Stay within
  the existing restore workflow; no rehearsal or extra deployment gate.
- Preview remains stopped. Later use a new explicit
  `local_only/reminder-preview.db`, never the helper's shared default or
  `--fresh` on existing data; confirm port 8080 ownership and use a visible pane.
- Evidence limits: no attached Android emulator found; physical Android/iPhone
  push, production Serverless and VAPID provisioning remain rollout limits,
  not automated passes. Use fake senders and disposable databases only.
- Children/workspaces: none created; Lead owns the entry workspace lifecycle.
- Docs-desk window: status-only preflight record; release immediately after
  committing this file. Further writes require another coordinated window.

## Closeout — assigned Conductor

- Result/change IDs: pending.
- Independent review and checks: pending.
- Assumptions, limits and retained artifacts: pending.
- Child cleanup/entry cwd release: pending.
- Owner review/acceptance: pending; no deployment.
