# Reminders S4: Phone Web Push

Lifecycle: tracked

## Brief — frozen at handoff

**Outcome/scope:** Implement approved stage 4: maintained Python Web Push sender, VAPID config, endpoint-owned subscription lifecycle, explicit feature-detected permission/enrollment/install flows, test button and disable/resubscribe, existing service-worker push/click handling, compatible visible/declarative fallback. Reuse stage-3 schedules/outbox/limits.

**Edit seams:** src/reminders transport + authenticated same-origin device/room APIs/config; frontend enrollment/settings; existing /service-worker.js (preserve /sw.js kill switch, cache/update/offline safety). Dependencies through uv only.

**Integration dependencies:** Stage 3 reviewed/integrated before dependent
DB/API/UI/worker/scheduler integration. Lead sequencing amendment agreed
2026-11-04: pure transport/security foundation may start first in isolation.

**Current foundation-only handoff:** new `src/reminders/push_transport.py`,
focused fake-network/signing/endpoint/DNS/TLS/redirect/result tests, approved
`pywebpush` runtime dependency/lockfile. Do not edit the package `__init__`
(S2 owns foundations), DB, enrollment APIs, UI, worker or scheduler. Outcomes
and retry hints are pure transport outputs, not another retry engine. No real
provider calls/endpoints/key provisioning. Fresh independent review/Python
gates are required. Reconcile dependency locks after predecessors; no full
stage completion claim before integration and remaining behavior.
**Unblocks:** [S5](reminders-s5.md).

**Done criteria:** Standards-based phone push is implemented with generic/private defaults, supported/needs-install/denied/subscribed states and safe opt-out per room/device. Every push shows a visible fallback and safe same-origin navigation. No real endpoint enrollment, VAPID secret provisioning or external push provider send during implementation/tests.

**Verification:** Full Python/frontend/browser gates and deterministic sender/worker tests: signing with test keys; endpoint SSRF/redirect/private DNS/ownership defenses; 2xx/429/404/410/5xx/timeout/config errors, retry expiry, foreground dedupe, malformed payload, clicks/auth and worker upgrades. Report physical iPhone/Android closed-app delivery as unverified; never substitute desktop WebKit evidence. Full commands live in the master plan's
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
- Planned owner: dedicated visible Pi Conductor `listr-reminders-s4`.
- Verified model: `openai-codex/gpt-6.1-sol`, effective thinking `high`;
  peer environment matches the explicit launch setting.
- Repository: `/home/hsa/projects/list_app`.
- Lead aggregate: `tmp-reminder-delivery`, `/home/hsa/projects/tmp-reminder-delivery`.
- Entry workspace: `tmp-reminders-s4`, `/home/hsa/projects/tmp-reminders-s4`;
  Lead-created/agent-managed; initial preflight @ `twuqsnnx`, base
  `rptqkywz` / `72b25032`. Independent foundation base is amendment change
  `vyvtntwv`, supplied exactly at the Lead edit handoff. Conductor freshly
  confirmed Sol/high, quiescence and Lead entry-update permission. Lead will
  supply reviewed S3 before dependent implementation/stage integration.
- Peer: `01a1a2ff-4fcb-7503-803f-e651fb9d7e45`.
  Zellij `pc-home`, tab 13 **ListR S4 phone push**, pane `terminal_22`.
  Normal Fish shell, target cwd and foreground Pi launch verified.
- Child fanout: workers and independent review authorized within this brief;
  isolated concurrent editors, no unrestricted recursive delegation.

## Status — assigned Conductor writes after handoff

- State: partial transport foundation independently reviewed and verified in S4
  entry only; quiescent. Full S4 remains blocked on reviewed S3 integration.
- Stable foundation tip: `ooywutkn` / `c23ab8a3`, based on `vyvtntwv` / `f43d01ca`.
  Entry `twuqsnnx` / `bdf37564` is an empty child above it. No Lead aggregate or
  dependent-stage integration; no bookmark moves.
- Next: Lead-coordinated reconciliation and exact reviewed S3 base before the
  remaining DB/enrollment/API/UI/worker/scheduler work. Reconcile dependency locks
  and rerun combined gates then; current foundation is not full-stage evidence.
- S2 seam: installation cookie/access, revision/idempotency and settings.
  S3 seam: transport results, leases, stable groups, expiry, live grant/state
  revalidation outside DB lock, quota/cross-day retries and blocked-push fallback
  without duplicate foreground strips. S5 receives operational notes/evidence limits.
- No live children or services. Owned transport child was removed after its
  reviewed work and artifacts were preserved. Lead retains S4 entry lifecycle.
- Sole Status/Closeout window granted after quota-interruption recovery. Earlier
  timed-out requests granted no edits. Commit this file only and release window;
  `integration` and `main` remain fixed, including for this docs-only change.

## Closeout — assigned Conductor

### Partial foundation only — full stage still open

- Result: `rzknzosp` / `ff5401a6` → `yrluorsp` / `43a93cc3` → `ooywutkn` /
  `c23ab8a301167b0a4f47a1bcd88433e46085306b`. Exactly four tracked files:
  `src/reminders/push_transport.py`, `tests/test_push_transport.py`,
  `pyproject.toml`, `uv.lock`. No package `__init__` or dependent runtime changes.
- Delivered: maintained pywebpush encryption/VAPID with injectable pinned HTTPS,
  public-only actual-connect DNS/IP validation, original TLS hostname/Host,
  no redirects/proxies, bounded DNS capacity/I/O, UTC/elapsed-time TTL checked
  after signing, secret-safe validation and typed outcomes without retry scheduling.
  Library API/source inspected; pywebpush 2.5.0 locked. No existing package
  versions changed; sixteen transitive packages added.
- Workers: implementation `c6da6314`, fixes `05c27137` → `e66334db`; actual
  Haiku5.5/medium verified. Medium review `590717ab` lacked committed-diff/shell
  access; escalated to fresh independent max reviewer with worker toolset
  `9d8195df` → re-review `6a9bebe8`. Actual Haiku5.5/max verified; final verdict
  ACCEPT for foundation only. Signer-expiry/budget and caller-contract findings
  fixed and independently re-reviewed; all three new regressions fail on old code.
- Parent gates on the S4 entry: required Ruff format/check-fix, full pytest
  **1655 passed, 9 skipped**, then format-check, Ruff and ty clean. Focused
  transport tests **120 passed**. Formatting/checks left no tracked edits.
  Frontend/browser lanes not run for this Python-only foundation.
- Retained evidence: `/home/hsa/projects/tmp-reminders-s4/.pi/reminders-s4-foundation/`
  contains `report.md`, `verification.log`, `final-review.md` and prior reports.
  These ignored artifacts survive child removal; Lead must preserve them before
  eventual S4 entry removal. Original subagent reports also remain in session artifacts.
- Cleanup: S4-created `tmp-reminders-s4-transport` was forgotten and its directory
  removed after reviewed reachability in entry, clean child, no live cwd users and
  artifact preservation were verified. No live child remains. S4 entry retained.
- Limits: exact FCM/Mozilla hosts and Apple push subdomains only; not universal
  provider support. A stuck resolver occupies at most four process-wide daemon
  slots; further lookups fail fast until capacity returns. Ambiguous attempts may
  be repeated by a future caller; acceptance is not delivery or exactly once.
  TLS tested in-memory, not against a remote provider. Physical iPhone/Android
  closed-app delivery remains unverified. iOS16.4 baseline/18.4 enhancement and
  no-silent-push requirements remain for the later worker implementation.
- Owner review/acceptance: pending for full S4. No real sends, registration,
  services, secret provisioning, production changes, deployment or bookmarks.
  Remaining full-stage behavior waits for the explicit reviewed-S3 handoff.
