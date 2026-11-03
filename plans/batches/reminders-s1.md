# Reminders S1: Quiet due center

Lifecycle: tracked

## Brief — frozen at handoff

**Outcome/scope:** Implement stage 1 of the approved plan: replace navigation/periodic due toasts with the scoped bell/panel, due grouping, list counts, date labels and safe item navigation. Reuse current room data, dialogs, themes and offline snapshots. No backend/schema, personal policies or push prompts.

**Edit seams:** Frontend due-reminders, PageShell, room/list headers, RoomLists, ItemRow and new focused reminder UI modules; corresponding Vitest/browser tests and current behavior/UX docs.

**Dependencies:** Implementation is approved; no predecessor stage.
**Unblocks:** [S2](reminders-s2.md).

**Done criteria:** No repeated navigation/reload warning; all due groups, room/list/share isolation, live/offline/rollover updates, filtered/deleted-target navigation and accessible keyboard/focus/color behavior are tested. Normal error/undo toasts remain.

**Verification:** Run frontend format/lint/check/unit/build and the full browser suite `uv run pytest browser_tests -q -n 4`. If Python test files change, run the full Python gates too. No real phone prerequisite. Full commands live in the master plan's
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
- Planned owner: dedicated visible Pi Conductor `listr-reminders-s1`.
- Verified model: `openai-codex/gpt-6.1-sol`, effective thinking `low`;
  two-way readiness acknowledged before edits.
- Repository: `/home/hsa/projects/list_app`.
- Lead aggregate: `tmp-reminder-delivery`, `/home/hsa/projects/tmp-reminder-delivery`.
- Entry workspace: `tmp-reminders-s1`, `/home/hsa/projects/tmp-reminders-s1`;
  Lead-created/agent-managed; base `zpzpvuyl` (`9abc4e72`).
- Peer: `01a1a2f1-3b36-7354-b16b-8fe1f4db448c`.
  Zellij `pc-home`, tab 10 **ListR S1 due center**, pane `terminal_19`.
  Normal Fish shell verified before launching foreground Pi; cwd/model/thinking
  verified by peer environment and pane metadata.
- Child fanout: workers and independent review authorized within this brief;
  isolated concurrent editors, no unrestricted recursive delegation.

## Status — assigned Conductor writes after handoff

- State: active; two-way readiness and explicit edit handoff received.
- Next: resumed worker finishes missing share/deleted-target coverage and
  preserves a stable completed tip; fresh review and combined full gates follow.
- Runtime checkpoint: initial worker reached the harness 30-minute timeout;
  partial scoped work remains in `kxumoykk`. Same worker resumed once as
  `04e1ec55-9fb2-4155-af65-fd3c65031ed3`, no harness/model substitution.
  Broader focused browser run had 103 passes and two WebKit offline failures
  plus teardown errors; serial offline 15 passed, but parallel failures remain
  unresolved until investigated and the required full `-n 4` gate passes.
- Child: worker run `5b6c7408-2f4f-487d-9264-092304820d4e`; native runtime
  status verified `claude-code/claude-haiku-5-5`, thinking `medium`.
- Provisional milestone: scoped due center, grouping/clock/reveal, headers,
  card counts, date labels and current-behavior docs implemented. Worker output
  reports 1,085 unit tests and 12 focused browser tests passing; final worker
  checks, independent review and combined stage gates remain pending.
- Independent review must cover room/share boundaries, midnight/visibility/
  offline refresh, filtered/deleted-item reveal/focus and every theme/mode's
  contrast, as well as the full Stage 1 contract.
- Child workspace: `tmp-reminders-s1-ui`,
  `/home/hsa/projects/tmp-reminders-s1-ui`, created/managed by this Conductor;
  initial change `kxumoykk` from completed base `zpzpvuyl` (`9abc4e72`).
  Worker alone edits frontend, related tests and current-behavior docs there;
  no grandchildren. Conductor owns reviewed integration and child cleanup.
- Docs-desk write window granted by Lead for this status update only;
  record-only commit and release reported through intercom.

## Closeout — assigned Conductor

- Result/change IDs: pending.
- Independent review and checks: pending.
- Assumptions, limits and retained artifacts: pending.
- Child cleanup/entry cwd release: pending.
- Owner review/acceptance: pending; no deployment.
