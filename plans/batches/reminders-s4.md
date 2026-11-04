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

- State: preflight accepted; quiescent, blocked by reviewed S3 integration.
  Two-way readiness verified; brief/master read fully and provisional seams inspected.
- Next: coordinated entry rebase and exact-base Lead EDIT HANDOFF. No
  implementation, children, services or notification enrollment/sends yet.
- Decomposition: subscription/API/security contracts, then sender/outbox;
  isolated frontend/worker work; fresh independent review and combined gates.
- Transport requirement: validate actual-connect DNS/IP/TLS and reject redirects,
  not only pre-resolve an endpoint. Lead approved a small injectable/pinned HTTPS
  transport or maintained crypto/VAPID with separately tested transport; reconfirm
  library APIs at implementation and escalate concrete unresolved seams only.
- S2 interface: installation cookie/access, revision/idempotency and settings seams.
  S3 interface: transport results, claims/leases, stable group IDs, expiry,
  saved-grant cancellation, shared quota/cross-day retries and blocked-push fallback
  without a duplicate foreground strip. Bind exact symbols after predecessor lands.
  S5 handoff: config/rotation/recovery notes, safe diagnostics and evidence limits.
- Assumptions: iOS16.4 installed-app baseline; WebKit18.4 declarative enhancement,
  never silent push. Push remains off without explicit configuration; fake sender
  and test keys only. Physical-device closed-app delivery remains unverified.
- Children/workspaces: none created; Lead retains entry workspace lifecycle.
- Docs-desk status-only window granted for this update; release after file-only
  commit. No bookmark moves; further writes require another coordinated window.

## Closeout — assigned Conductor

- Result/change IDs: pending.
- Independent review and checks: pending.
- Assumptions, limits and retained artifacts: pending.
- Child cleanup/entry cwd release: pending.
- Owner review/acceptance: pending; no deployment.
