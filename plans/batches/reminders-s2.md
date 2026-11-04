# Reminders S2: Personal policies, dates and previews

Lifecycle: tracked

## Brief — frozen at handoff

**Outcome/scope:** Implement approved stage 2: installation/enrollment identity and private APIs, device/room/list/item policy inheritance, presets and five effective relative/fixed reminder rules, optional shared due time/zone with canonical server due_at, one resolver/preview and complete offline/undo/feed compatibility. No real scheduling or push sends yet.

**Edit seams:** src/reminders, src/api/reminders and existing item ops/CRUD/migrations/feed; frontend types/validation/offline overlays, reusable reminder editor/settings and previews. Keep personal data out of shared feeds and share-link APIs.

**Integration dependencies:** Stage 1 reviewed/integrated before dependent UI
or stage integration. Lead sequencing amendment agreed 2026-11-04: the
independent backend date/time foundation may start first in isolation.

**Current foundation-only handoff:** pure server zoneinfo resolver; shared
`due_time`/`due_timezone`/canonical `due_at` and stable due-cycle migration,
CRUD/item ops/feeds; Python tests; approved runtime `tzdata`; directly related
API docs. No frontend, personal-policy API, scheduler or push yet. Obtain fresh
independent review and Python gates. Preserve result for reconciliation onto
reviewed S1; do not rebase active children or claim full stage completion.
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
- Verified model: `openai-codex/gpt-6.1-sol`, effective thinking `high`;
  peer environment matches the explicit launch setting.
- Repository: `/home/hsa/projects/list_app`.
- Lead aggregate: `tmp-reminder-delivery`, `/home/hsa/projects/tmp-reminder-delivery`.
- Entry workspace: `tmp-reminders-s2`, `/home/hsa/projects/tmp-reminders-s2`;
  Lead-created/agent-managed; initial preflight @ `ooqvyvmw`, base
  `rptqkywz` / `72b25032`. Independent foundation base is amendment change
  `vyvtntwv`, supplied exactly at the Lead edit handoff. Conductor freshly
  confirmed Sol/high, quiescence and Lead entry-update permission. Lead will
  supply reviewed S1 before dependent implementation/stage integration.
- Peer: `01a1a2ff-4ea8-70c1-b611-b0506e7b9929`.
  Zellij `pc-home`, tab 11 **ListR S2 schedules**, pane `terminal_20`.
  Normal Fish shell, target cwd and foreground Pi launch verified.
- Child fanout: workers and independent review authorized within this brief;
  isolated concurrent editors, no unrestricted recursive delegation.

## Status — assigned Conductor writes after handoff

- State: backend foundation implemented, not independently accepted; worker
  quiescent, review pending. Dependent UI/personal-policy work and stage
  integration remain blocked on reviewed S1 and a further handoff.
- Exact foundation base: `vyvtntwv` / `f43d01ca`; entry `ooqvyvmw` /
  `5b7b734b` was clean at handoff. Entry remains Lead-managed.
- Child created before launch: `tmp-reminders-s2-foundation`,
  `/home/hsa/projects/tmp-reminders-s2-foundation`; `zystrxzr` / `a52b6b41`
  initially empty on that base. S2 Conductor session `01a1a2ff-4ea8-70c1-b611-b0506e7b9929`
  owns its lifecycle, reviewed integration into S2 and safe cleanup.
- Worker run `104772f9-23a8-4526-9606-d90dbfe0f40e` completed with effective
  `claude-code/claude-haiku-5-5:medium` verified by receipt and environment;
  no descendants. Stable tip `zystrxzr` / `2e0f70a4`; clean empty child
  `umuktknn` / `228afc02`, no background processes. Seventeen changed files
  inspected: backend/test/runtime dependency/API-doc seams only.
- Initial fresh reviewer `2c5252fb-8a33-4329-9cf8-2f539ba77920` has medium
  verified by receipt, but preset lacks shell/env. Its static review is
  supplemental, not sufficient acceptance. Next: fresh `worker`-toolset
  read-only independent full base-to-tip review, explicitly Haiku5.5 medium;
  verify shell access/effective settings. No descendants, 60-minute deadline
  with five-minute checkpoint. S2 owns review runs, existing cwd and cleanup.
- Worker scope: pure server resolver, shared due fields/canonical UTC/cycles,
  migration/CRUD/item ops/feeds, Python tests, runtime tzdata and related API
  docs only. No frontend, personal-policy API, scheduler, push or real services.
- Obtain fresh independent diff review and full Python gates on the combined
  foundation. Preserve a stable reviewed tip and quiescence for Lead's later
  reconciliation; never rebase an active writer.
- Python evidence: worker full gates passed; Conductor separately reran
  Ruff format/lint checks, ty and full pytest: 1,581 passed, nine skipped.
  Existing absent local frontend-build notice remains; no browser gates run.
- Image evidence: trusted unchanged Dockerfile built successfully with rootless
  Podman as `localhost/listr-s2-foundation:zystrxzr`, image `18e87471956c`;
  locked no-dev install included runtime tzdata 2026.6. Network-disabled,
  read-only smoke (no mounts/server) passed with `PYTHONTZPATH=''` and empty
  `zoneinfo.TZPATH`: Oslo gap/fold, canonical UTC, date-only and multiple zones.
  Existing frontend npm audit summary surfaced during build; no frontend
  dependency changes attempted.
- Compatibility: test absent/null/legacy hashes and undo/conflict semantics;
  use the existing API-version mechanism only if required, with rationale.
- S3 handoff must document/test concrete resolver/effective-policy exports,
  installation/enrollment grant validation, due-cycle and stable fixed-rule
  identities/instants, revisions/idempotency and future-only activation time.
  S3 owns persisted occurrences/outbox/quotas/leases and the scheduler.
- Docs-desk: ownership recorded in the granted status-only window before
  worker launch; future writes require another window. Brief remains Lead-owned.

## Closeout — assigned Conductor

- Partial result: foundation `zystrxzr` / `2e0f70a4`, not full S2 completion.
- Independent acceptance/own-line combined checks: pending. Worker and
  Conductor child checks/image smoke above do not replace independent review.
- Retained artifact: Pi subagent output `104772f9-23a8-4526-9606-d90dbfe0f40e/foundation-worker.md`.
  API version stays additive (legacy hashes preserved); resolver exports are
  provisional until reviewed. No dependent contract readiness claimed.
- Child cleanup/entry cwd release: pending.
- Owner review/acceptance: pending; no deployment.
