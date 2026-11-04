# Reminders S1: Quiet due center

Lifecycle: tracked

## Brief — frozen at handoff

**Outcome/scope:** Implement stage 1 of the approved plan: replace navigation/periodic due toasts with the scoped bell/panel, due grouping, list counts, date labels and safe item navigation. Reuse current room data, dialogs, themes and offline snapshots. No business API/schema, personal policies or push prompts.

**Edit seams:** Frontend due-reminders, PageShell, room/list headers, RoomLists, ItemRow and new focused reminder UI modules; corresponding Vitest/browser tests and current behavior/UX docs.

**Agreed verification repair (2026-11-04):** S1 owns narrow diagnosis of the
observed empty app-shell cache and full-gate offline/focus failures. Allow
throwaway telemetry and a minimal evidence-backed repair in the existing
worker, registration, dialog and browser harness; `src/pwa_routes.py` only for
its legacy retirement script if implicated. Preserve one worker, current
cache/privacy/update/offline contracts and `/sw.js` retirement; no dependencies
or environment changes. Attribute cache creation/deletion to a worker/version/
client timeline, inspecting names before `caches.open` can create a cache.
Use identical unchanged common tests/build/`-n 4` conditions for comparisons;
a lower-load baseline cannot prove attribution. Keep a proved repair in a
separate atomic change, remove throwaway logging, obtain fresh independent
max diff review and pass relevant full gates. No speculative fix or flake waiver.

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
  two-way readiness acknowledged before edits. For the expanded hard
  lifecycle phase, select Sol/high and verify effective thinking before edits;
  report unsupported control rather than silently retaining/substituting a level.
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

- State: active, full browser gate blocked. Expanded verification-repair
  edit handoff received after `ulunnpkv` (`0ad7b06c`); Brief/Assignment frozen.
- Latest baseline evidence: ONE full unchanged pre-S1 browser suite in owned
  baseline workspace, `uv run pytest browser_tests -q -n 4`: 398 passed,
  1 failed (WebKit cold-offline-deep-link: cache entries empty before stop).
  Log `/tmp/listr-s1-baseline-full.log`. The symptom predates S1; this is
  neither a root cause nor a gate waiver.
- Expanded max investigation `a961e904-f3db-4682-a084-94fa71bc6cc7` made
  no fix. Corrected instrumented run: 440 passed/1 failed/1 error, active cache
  empty with no observed wrapped-worker delete. Another run was INVALID:
  diagnostic put wrapper dropped arguments. No eviction attribution accepted.
- Fresh max causal run `c0d351a1-8998-49bc-a2ac-957fecfcf6e4`: INCOMPLETE.
  It mapped writer sites and passed clean focused tests (3 cold-link, 30 worker
  file), but did not implement required attribution instrumentation. It found
  stale telemetry in the ignored build, rebuilt marker-free, and left source
  clean. Baseline build had no telemetry markers. No model substitution.
- Next dispatch, agreed with Lead: fresh shell-capable Haiku 5.5/max worker,
  instrumentation IMPLEMENTATION ONLY in owned UI child, explicit runtime/
  checkpoint. Conductor Sol/high owns collector acceptance and later causal
  analysis. Required: all-page/served-worker/legacy-context collector; names
  before open; native API success/error timeline; semantic self-tests proving
  this/all arguments/promise/error/body behavior; fingerprints and one focused
  targeted external trace. Enumerate blind spots, log no tokens/bodies.
  Preserve collector patch/self-tests/traces outside shipping changes, remove
  source telemetry and rebuild clean. No full-suite loop, speculative repair,
  dependency/environment change or acceptance. Actual proved repair remains
  separate atomic work requiring fresh independent max review/full gates.
- Conductor freshly verified from environment: session
  `01a1a2f1-3b36-7354-b16b-8fe1f4db448c`, cwd
  `/home/hsa/projects/tmp-reminders-s1`, provider `openai-codex`, model
  `gpt-6.1-sol`, reasoning `high` for this hard lifecycle phase.
- Actual completed candidate: `swtpolmk` (`d90bc864`) atop `kxumoykk`;
  integrated into clean entry `vsoywmwz` (empty child). Fresh max reviewer
  `863359a7-a6e4-4990-9824-f01cd37ef2be` read the complete 1,813-line
  base-to-tip diff and approved code conditional on full gates.
- Combined gates: Python 1,535 passed/9 skipped; Ruff format/check and ty
  clean; frontend format/lint/check/1,088 unit tests/build passed.
  Full `uv run pytest browser_tests -q -n 4`: 438 passed, 3 failed, 2 errors.
  Failures: Chromium keyboard reopen and WebKit saved-notice/legacy offline
  navigation. Log `/tmp/listr-s1-browser-full.log`; no flake waiver.
- Diagnostic max worker `589b5d6e-ef2a-42d1-86bc-1eb27d252e9a`, resumed
  `7a4dea45-cb87-443e-bfdd-50ab389e6fed`, finished without changes.
  Telemetry caught an activated worker with an empty named cache before
  shutdown; cache-emptying writer remains unknown. Keyboard did not reproduce
  in nine instrumented reopens. Lower-load baseline passes do not prove cause.
- Owned baseline child: `tmp-reminders-s1-baseline`,
  `/home/hsa/projects/tmp-reminders-s1-baseline`, empty `mznouxzm` from
  `zpzpvuyl`; Conductor-created/test-only, cleanup retained until evidence safe.
  UI child remains `tmp-reminders-s1-ui`, empty `xtwzoknt` above candidate;
  no active writer at this checkpoint. Conductor owns both child lifecycles.
- Next authorized dispatch: one bounded Haiku 5.5/max telemetry-first worker,
  verify effective runtime setting, identify cache writer/version/client timeline
  (names before open), compare identical unchanged common tests if useful,
  then only a proved minimal repair as a separate atomic change. No environment
  or dependency change; preserve worker/cache/privacy/update/retirement contracts.
  Remove throwaway logging, obtain fresh independent max diff review and rerun
  relevant full gates before completion. No feature acceptance or deployment.

### Earlier implementation checkpoints

- Initial candidate: completed `kxumoykk` (`30cf8d1b977f`), empty child `swtpolmk`.
  Actual worker environment confirms `claude-code/claude-haiku-5-5`, `medium`.
- Independent medium review `cdd5ba56-6485-4563-947e-a4be24c8f2a6`: BLOCK.
  Confirmed stale clock on remount, silent conflicting-filter clearing, doc
  contradiction and missing edge browser coverage. Reviewer admitted it did
  not inspect the base-to-tip diff; this is not final review approval.
- Fix worker `35e31c54-60b6-4b5c-9737-77900331ee1b` uses the same isolated
  child workspace, requested Haiku 5.5/max (effective verification pending),
  explicit 60-minute runtime with three-minute checkpoint. Scope: clock and
  lifecycle tests, restrained explicit filter-cleared status (not a due toast),
  doc correction and isolation/offline/live/keyboard/unavailable coverage.
  Fresh independent diff-level review is required after material fixes.
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
