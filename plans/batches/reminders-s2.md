# Reminders S2: Personal policies, dates and previews

Lifecycle: tracked

## Brief — frozen at handoff

**Outcome/scope:** Implement approved stage 2: installation/enrollment identity and private APIs, device/room/list/item policy inheritance, presets and five effective relative/fixed reminder rules, optional shared due time/zone with canonical server due_at, one resolver/preview and complete offline/undo/feed compatibility. No real scheduling or push sends yet.

**Edit seams:** src/reminders, src/api/reminders and existing item ops/CRUD/migrations/feed; frontend types/validation/offline overlays, reusable reminder editor/settings and previews. Keep personal data out of shared feeds and share-link APIs.

**Integration dependencies:** Reviewed S1 remains required before frontend
wiring or full-stage/aggregate integration. Lead/Conductor sequencing amendment
agreed 2026-11-04: after the date/time foundation's independent review and
own-line gates, the server-only identity/policy/preview milestone may proceed
on that stable foundation, without waiting for S1's independent browser repair.

**Current server-only handoff:** Keep the shared date/time/cycle foundation;
add installation identity, enrollment/saved grants, private settings/policy APIs
and pure effective-policy/next-five preview. Use current SQLite/FastAPI and
foundation resolver. No frontend, lifespan scheduler, occurrences/outbox,
quota dispatch, subscriptions, push or outgoing reminders. Full S2 remains open.

- Contract/tests first: scoped revisions/idempotency, hashed server-issued
  installation secret, live room-token hash/authorization-version binding,
  explicit enroll/resume and no silent reactivation. Private APIs need current
  room plus device authorization; GET/preview must not create/renew installation
  identity or grants. No arbitrary-installation-ID access or personal feed leaks.
- Store validated device settings and room/list/item replace/off/inherit/reset
  policies per approved product contract, including five normalized relative/
  fixed rules, stable fixed identities and future-only activation. Narrow
  sign-out/password-reset/deletion hooks only as needed for grant correctness.
- Pure preview shares the foundation resolver, uses confirmed `due_at`, and
  reports inheritance, explicit zones, fixed/relative identity, quiet deferral,
  coalescing and disabled states. No side effects or second scheduling engine.
  Bind concrete exports for S3 only after independent review; provisional names
  are not a ready contract. Prefer preview naming distinct from S3's evaluator.
- Split into reviewable bounded children at stable contract boundaries. Fresh
  independent full diff/code/test review and full Python gates for each usable
  milestone; include migration/cookie/privacy/revocation/revision/idempotency,
  inheritance/rule/DST/quiet/future-only and side-effect tests. API/security docs
  stay with code. Browser/UI gates remain for the later wired full stage.
- Preserve reviewed results for later reconciliation onto S1; never rebase an
  active writer, reduce approved behavior or claim full-stage completion.
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
  supply reviewed S1 before frontend/full-stage integration. Current server-only
  milestone base: completed `umuktknn` / `62d6834c`, reviewed and verified on the
  S2 line; empty entry `ooqvyvmw` / `e90bf385`. No entry rebase is needed.
  Create new owned backend children from that completed tip, not the empty entry.
- Peer: `01a1a2ff-4ea8-70c1-b611-b0506e7b9929`.
  Zellij `pc-home`, tab 11 **ListR S2 schedules**, pane `terminal_20`.
  Normal Fish shell, target cwd and foreground Pi launch verified.
- Child fanout: workers and independent review authorized within this brief;
  isolated concurrent editors, no unrestricted recursive delegation.

## Status — assigned Conductor writes after handoff

- State: foundation and identity A reviewed/integrated into S2; proceeding to
  server-only policy/cycle-cutoff B under existing handoff `yxsowmmv` /
  `5f187aad` and accepted expiry/activation clarification `vlsuxkvn` /
  `ac59b242`. Frontend/full-stage integration still awaits S1.
- Accepted source now includes B cycle-start slice `rwswntvl` / `3eb72704`;
  clean S2 entry `ooqvyvmw` / `6990d1e6`, still Lead-managed.
- Remaining B is split into pure rules B2a, policy storage/inheritance/activation
  B2b, then private API B2c; separate C preview follows reviewed B. No policy
  storage/API or preview exists yet. Contract/tests and independent review per slice.
- Retained unfinished child: `tmp-reminders-s2-policies`,
  `/home/hsa/projects/tmp-reminders-s2-policies`, from completed `wyknnmnm`,
  not empty entry. S2 Conductor `01a1a2ff-4ea8-70c1-b611-b0506e7b9929` owns
  child creation, lifecycle, reviewed integration and cleanup. Do not remove it
  while B remains unfinished; no concurrent writers.
- Broad medium `e56a6054` delivered only the cycle-start slice; broad MAX
  `ee1ca186` delivered only GET-cookie doc correction `potqzyxv` / `2d875515`.
  Neither delivered policy code; both completed, no false B completion claim.
- Active bounded B2a `da82dd80-9dae-4085-a386-936d1feb3737`: fresh shell-capable
  Haiku5.5 medium (native settings verified), pure `rules.py` and its tests only,
  source base `potqzyxv` / `2d875515`, initial empty `ovwlmwsw` / `782f2b9f`.
  Forty-minute deadline/five-minute checkpoint; no descendants. Source/tests
  written, not reviewed. Repeated malformed edit arguments were rejected before
  mutation; exact array schema supplied for one retry, otherwise checkpoint/stop.
- Subsequent reviews read actual source/docs/tests, including the enumerated
  GET-cookie bullet and live GET probe; no inference from an accuracy claim.
  Routine run/check evidence stays in Pi artifacts; batch Status updates here.
- Edit bounds: reminder policy/domain/storage/API, next migration and narrow
  cycle mutation/restore hooks, Python tests and related current API/security
  docs. Existing identity/security contracts preserved. No frontend,
  scheduler/lifespan task, occurrences/outbox,
  quota dispatch, subscriptions, push, production config or real services/sends.
- Routine assumptions: GET/preview never enroll or renew grants/cookies;
  install-only grants no room access; explicit resume after sign-in; saved grant
  validation and separate installation/enrollment idempotency/revisions tested.
  Concrete S3 exports remain provisional until milestone review.
- No bookmarks move, including docs-only `integration`; commit only this batch
  Status/Closeout during granted windows. Brief/Assignment frozen and Lead-owned.

## Closeout — assigned Conductor

- Foundation partial result: `zystrxzr` / `2e0f70a4` plus doc/test review fixes
  `umuktknn` / `62d6834c`. Not full S2 completion or feature acceptance.
- Author medium run `104772f9` and fix resume `9e6ddf85` complete. Static medium
  review `2c5252fb` supplemental; shell medium `b0e87a1f` requested doc/test
  fixes but omitted some test assertions. Fresh shell MAX `a94a73b2` approved
  the complete final 18-file/1,899-line delta and all new assertions.
- Own-line checks after reviewed child integration: `uv sync --locked`; all
  required Python gates passed, 1,593 passed/nine skipped (54.82 seconds),
  Ruff format/lint and ty clean, zero working-copy diff. Reviewer's two PATH-only
  deploy-backup failures reproduced on baseline, not in the uv-managed gate run.
- Nonblocking limits retained: extreme calendar overflow safely rejects with a
  misleading generic message; timed unchanged-schedule rename under missing
  zone data independently works but lacks a repository assertion. No UI/browser
  gates claimed for the server-only lane.
- Image/audit evidence: [delivery verification](../../docs/background/reminder-delivery-verification.md).
  Image `18e87471956c` retained; network-disabled/no-mount/read-only zone-data
  smoke also passed after child deletion. No production services started.
- Foundation child `tmp-reminders-s2-foundation` forgotten and folder removed:
  all runs complete, no cwd users, clean child/result reachable from S2 first.
  Five author/review reports retained outside that child under this Pi session's
  `subagent-artifacts/outputs/`; no path-dependent artifacts lost.
- Identity A partial result: `ozrsznyk` / `f082a8dc`, required fixes
  `ztyquuxl` / `350f9f55`, room-scoping fix `wyknnmnm` / `a8ee483a`.
  Medium review `5625b841` found four required fixes; MAX full review
  `e36aaeab` verified those, found wrong-room sign-out scoping, then MAX
  delta re-review `b99cd259` approved the exact final tip with mutation/control
  probes. All author/review runs completed; no source acceptance by self-review.
- A own-line full Python gates: 1,665 passed/nine skipped (49.01 seconds),
  Ruff format/lint and ty clean, zero diff. Explicit persisted installation/grant
  expiry, action-discriminated idempotency, in-lock dynamic replay state and
  room-scoped atomic revocation are reviewed. No ordinary room-auth age change.
- A child `tmp-reminders-s2-identity` forgotten/folder removed after clean,
  reachable result/no cwd users. External Pi artifacts retained:
  `2b016c10-f314-478c-87b0-8324b59000b3/identity-worker.e5969d2c.a8f9f9b4.md`
  and `e36aaeab-69fb-4083-9b77-bd2e93b5f72c/identity-final-review.b99cd259.md`.
- A limits: lost first response may leave an unused installation; token-cap
  pruning can leave stored status stale, but live grant validation is authoritative.
  Lead found an actual doc discrepancy despite `b99cd259`'s accuracy claim:
  GET device was wrongly listed among 403 routes. Doc-only `potqzyxv` /
  `2d875515` fixes the enumeration, pending follow-up review with B2a.
- B cycle slice: `ozkolnnz` / `dd1832db` plus test-only `rwswntvl` / `3eb72704`.
  Medium independent `0af1150b` source review plus `374eca1b` exact-clock
  delta approval; four mutations prove wrong clock/per-row/format/undated cases
  fail. Own-line Python gates: 1,688 passed/nine skipped (55.15 seconds),
  Ruff/ty clean, zero diff. Only shared cycle-start metadata/cutoff helper done.
- B slice limits: undated SQL arguments still sample a clock but store NULL;
  cutoff helper tests are not scheduler end-to-end evidence and require aware
  timestamps from future callers. Broader B/C remain unimplemented.
- External Pi reports retained for `e56a6054`/`600f3a2f`, `0af1150b`/`374eca1b`,
  and doc-only MAX `ee1ca186`. Unreviewed draft rules tests are outside repository
  at `/tmp/policies-worker-drafts/`, not delivered code.
- No policy/preview/S3-ready contract yet. Lead entry remains open/clean; no
  cleanup above S2 ownership. B child/results/review/cleanup pending; no deploy.
