# S3 scope review: a small in-app reminder release

Research and proposals only. **S3 remains on hold. Nothing below is implemented
by this review.** The [assignment](../../plans/reminders-s3-scope-review.md)
owns the task; the [overnight record](../../plans/night-run.md) owns delivery.

## Owner summary

**Recommend A: an opt-in daily brief while the app is open.** Do not recover the
whole archived S3 runtime for five users.

- **New benefit:** the app offers one quiet summary instead of waiting for the
  person to open the due bell. A private daily record remembers that this device
  was offered the brief and whether the person dismissed it. Reloading or using
  two tabs does not offer another brief for the same room and day.
- **Example:** a brief is set for 09:00. You first use that room at 09:20 and see
  “3 items need attention”, with **Open due items** and **Dismiss**. The due bell
  remains the live list. Dismiss does not complete items or clear due counts.
- **Limits:** no alert with the app closed; no reliable hidden-tab or phone
  delivery. No earlier-day backlog. New items after today's brief remain in the
  bell, not another prompt. This is a convenience, not an alarm.
- **Small scope:** one daily time, timezone, pause/off, one restrained prompt and
  recent summary records. No custom schedules, item/summary snooze, extra overdue
  repeats, or **Remind me now**. Advanced personal editors remain hidden.
- **Recovery:** retain all archived sources. Reuse accepted identity/time rules
  and selected safety/test patterns. Build a narrow foreground claim and UI on
  the accepted app; do not import the old scheduler and ten migrations.
- **Cost:** moderate, not trivial. Private state, duplicate prevention, restore
  safety and phone-width UI checks remain necessary. B adds much more runtime
  work. C defers all new behavior and has the lowest immediate cost.

**Two material owner choices:** choose A, B or C; and, for A/B, allow a limited
in-app setup before phone push. Default recommendation: **A, with only its small
setup exposed after review**. This changes the old broad release scope and the
“settings hidden until phone notifications are ready” policy. No such change
is approved by this report. See [the choices](#material-owner-choices).

## What is current, and what is not

The **accepted behavior baseline is frozen at
`9e34df13e5b773ebf88032047fbe26a1088877bb`**. It includes production-line
`250c17b669605cea59bd671ba7e9e49ee3dcbce6` and accepted S1/S2/P/P2. The research
workspace starts at merge `762c384b9aa5e4acd4ee90012ae6df22eb92b98a`. That merge
also carries earlier *unaccepted* test changes, docs and theme drafts. It is
not the product baseline. Parked S3 is not accepted behavior either.

Actual accepted code has:

- S1's room/list/share-scoped due bell, live due counts, date groups, item reveal,
  saved-data display and foreground day/time refresh. It has no reminder toast.
- S2's shared due time/zone and confirmed UTC instant, private device/room
  identity and policy APIs, a resolver and preview. Saving a schedule is not
  delivery. There is no occurrence inbox, strip or scheduler in this baseline.
- P2's `PERSONAL_REMINDER_SETTINGS_ENABLED = false`. The personal components
  and APIs remain, but their UI entry points are hidden. Merely visiting a room
  does not create an enrollment or authorize future reminders.

Thus a new due panel, badge, date grouping, offline due list, or next-time
preview would **not** be a useful new S3 release. A adds only a proactive daily
offer and private durable handling state. The bell stays the single live due
view; a second copied due list is not proposed.

Sources: [current-source analysis](reminders-s3-scope-review-evidence/current-source-analysis.md),
[file comparison](reminders-s3-scope-review-evidence/baseline-fit-manifest.json),
and [current due behavior](../due-date-reminders.md). Exact code references in
the analysis, not old plan completion labels, establish the behavior boundary.

### Existing documentation contradictions

These are findings, not changes to policy or architecture:

1. The live [architecture](../../ARCHITECTURE.md) says the device cookie holds
   the secret's hash. Accepted `src/api/reminders.py:303` puts the random secret
   in the HTTP-only cookie; `src/reminders/identity.py` hashes it for database
   lookup/storage. The [API contract](../api-reminders.md) describes that split.
   Future implementation should agree a documentation correction, not change
   the security design silently.
2. The current behavior doc says settings stay hidden until **phone** delivery
   is ready. The master's progress and frozen S3 brief say **S3** restores them.
   Architecture describes the foundation but does not explain the hidden UI.
   A needs an explicit limited exception; flipping P2's whole switch is not it.
3. The current due doc describes a room-scope switch from a list. The accepted
   polished component does not expose that switch. Preserve actual list/share
   scope; do not use this stale sentence to broaden private reminder access.

## Three options — proposed, not current

| Option | Useful gain and example | Scope, settings and recovery | Effort, uncertainty and later stages |
| --- | --- | --- | --- |
| **A. Foreground daily brief — recommended** | On the first eligible use after 09:00, offer the room's current overdue/today/tomorrow items once. A private daily record stops reload/tab repetition. | Explicit device/room opt-in; small summary setup, prompt and recent records. No background scheduler, advanced timing, snooze, manual alert or phone permission. Reuse accepted foundations and safety patterns; rebuild the small claim/UI seam. | **Moderate**, with a bounded new state model and UI/security checks. Smaller than recovering S3. S4 later needs scheduling/outbox work; this is not a push-ready runtime. S5's relevant UI/privacy/restore checks are needed before A ships. |
| **B. A plus one at-due reminder** | A person working in the app can also get a prompt when a confirmed future item reaches its due anchor, rather than waiting for tomorrow's brief. | Add one at-due rule only, durable generation/recovery and a supervised scheduler. Date-only items use the configured all-day anchor; timed items use confirmed UTC. No custom offsets/fixed rules, snooze/repeats/manual alerts or push. Narrow settings, with future-only activation. Selective recovery of core/claim/restore modules is worth a new compatibility review. | **High relative to A**: scheduling, cancellation, stale work, shared-device limits and lifecycle seams return. Closed/background display still cannot be promised. More reusable for S4, but no automatic approval to resume S4. S5 has a larger regression surface. |
| **C. Defer new reminders** | Keep today's quiet due information. Best if people do not need a prompt while already using the app. | Leave P2 hidden; no new private state or UI. Retain the archive and current accepted app. No recovery or implementation now. | **Lowest immediate effort/risk.** No new reminder benefit. S4 still needs a later approved S3 contract/runtime; S5 stays paused. Avoids maintenance for a feature that might not earn its place. |

A earns its place only if a brief on opening/returning is useful to these users.
It cannot remind someone to open ListR. If that is the real need, choose C until
phone work is worth resuming; do not make A look like a phone alarm. B's extra
value is narrow compared with its state and testing cost, so it is not the
recommended first release. A needs no always-running background tick. B would
also need the hosting sleep setting checked at a later approved rollout: a
sleeping server cannot wake itself for a due time. No live hosting setting was
read or changed in this review.

## Proposed A contract

This section is a draft for a later approved brief, not implementation authority.

### Trigger, cadence and content

- Off until an explicit **Enable daily brief on this device for this room**
  action. New setup defaults to 09:00, Europe/Oslo; keep an existing saved zone.
  Show the next eligible day/time. Do not silently activate an old S2 grant,
  saved custom schedule, or policy preview.
- Check on authorized room entry, visible-page return, and the existing minute
  refresh **only while visible and connected**. The server decides eligibility
  from confirmed data and one clock. A page timer is only a request trigger.
- Offer the first **nonempty** eligible brief at or after its daily time, subject
  to quiet hours and the shared device's cap/spacing. Preview any quiet-hour
  adjustment; flag a time that cannot produce a same-day brief under the saved
  quiet window. Enrollment/resume/time or zone edits activate future anchors only. Enabling at 10:00 does not replay the
  earlier 09:00 brief. No claim for an empty summary.
- At most one offer for a device, room and local calendar day, including after
  reload, settings edits, resume, or a tab race. Quiet/spacing deferral may offer
  it later that day; never replay a previous day's missed brief. Current Off,
  pause, opt-out and live authorization always win.
- Include current unchecked items overdue, due today or due tomorrow. Reuse S1's
  semantics and server-confirmed timed dates. Exclude done/deleted/undated items
  and inaccessible targets. A completed item is not kept merely because it was
  due earlier. Each item appears once.
- After that day's offer, new or changed items remain discoverable in the bell;
  they do not generate another offer. An overdue item can occur in the next
  day's brief until completed; there is no extra per-item repeat alert.
- One non-modal strip, no focus grab, no blocked add bar, no navigation toast.
  **Open due items** opens the existing scoped bell; **Dismiss** acknowledges
  this brief. A persistent entry allows a missed strip to be handled later.
  Keep due counts separate from summary-handling state.

### Private acknowledgement, duplicates and recovery

- The daily offer and dismissal belong to **this installation in this room**.
  They survive reload, restart and another tab on that installation. Another
  device is independent. They never mark an item done or change shared dates.
- Persist the once-per-day claim and acknowledgement in SQLite, with atomic
  uniqueness and current authorization checks. Two tabs cannot both obtain a
  new offer. Retain anti-replay identity after recent records are pruned.
  Do not rely on a browser `Set`, local storage or broadcast hints for safety.
- Keep 30 days of recent summary metadata, not a new item audit history. Say
  **Offered** for a server handoff, not **Seen** or **Delivered**. Dismissal is
  an explicit acknowledged action. A lost response/crash may mean a brief was
  not seen; favor a missed prompt over repeated interruptions. Do not promise
  exactly-once human display.
- Revalidate room cookie, device cookie, current saved grant/binding, scope,
  pause/Off and live item relevance at the final claim and each private read or
  action. Do not accept a device ID as authority. Public shares cannot enroll,
  claim, acknowledge or read personal summaries.
- On sign-out, revoked access, device expiry, room deletion or unknown private
  context, stop new claims and clear visible/private in-flight state. Re-sign-in
  requires explicit resume and future activation. Offline sign-out stops local
  UI but cannot claim immediate server revocation before confirmation.
- Use a restore boundary that survives replacing SQLite. While restore state is
  missing, corrupt, paused, or cannot be held safely, offer nothing new. After
  resume, suppress anchors at/before the restore cutoff; a lost current-day
  brief is acceptable. This is a proposed conservative A rule, not the archived
  scheduler's strict-before cutoff for scheduled/snoozed work. The due bell
  still works. A stale claim must not outlive a grant change or a concurrent restore. Test actual claim/commit ordering,
  not only a helper's return value.
- No personal event content in room/share feeds, SSE, cross-tab hints or logs.
  Resolve names only from current authorized data. Recent deleted/inaccessible
  targets say unavailable. Operator database access is not private from the
  operator. Clear private UI on observed invalidation; do not claim that a
  response already shown can be recalled or a silent cookie change instantly
  detected.
- Personal setup/actions need a connection. Do not add another offline mutation
  queue or cache personal histories as part of this release. Unknown saves need
  refresh/review, not replay of an old body against a new installation.

These protections remain essential with five users. The smaller release removes
features and background work, not authorization or durable duplicate control.

## Keep, defer and drop for the first release

| Area | A decision | Reason in user terms |
| --- | --- | --- |
| Daily summary | **Keep**, foreground only | A small daily prompt plus saved handling state is the new benefit. |
| Shared due dates/times and bell | **Keep unchanged** | Already useful and accepted; they remain available with reminders off. |
| Advanced timing, offsets, fixed times, list/item editors | **Defer** | They add choices and cancellation rules before the daily prompt proves useful. Keep existing stored settings intact and inactive for delivery. |
| Item and summary snooze | **Defer both** | Dismiss today's brief; the bell remains available. Do not pretend dismissal means “remind me later.” Summary snooze was unfinished in the archive. |
| Separate overdue repeats | **Defer** | The next day's brief already includes unfinished overdue items. Avoid extra interruptions. |
| History | **Keep small** | Recent daily offers/dismissals help explain “why no second prompt?” No transport-state dashboard, unread badge, copied item snapshots or full event audit. |
| Manual actions | **Keep Open/Dismiss/Off; drop Remind me now from this release** | In an open app, another immediate reminder adds little beyond opening the due bell. The archived generation bridge is unfinished. |
| Quiet hours, cap/spacing and privacy | **Keep safeguards** | Switching among rooms must not create a stream of prompts. Do not present unused phone-text controls. |
| Push, retries, absence fallback | **Defer** | No phone transport exists in A. Do not ship speculative sender/accounting infrastructure. |

“Drop” here is product scope, not permission to delete archived code or history.

## Recovery evidence and exact sources

**Implemented, reviewed, tested, compatible and reusable are different claims.**
The archive owner summary and final checkpoint say S3 is incomplete, quarantined
and paused. Their historical component passes are not full-stage acceptance.

Exact source aliases below are immutable commits, not moving change prefixes:

| Alias | Exact source |
| --- | --- |
| Accepted | `9e34df13e5b773ebf88032047fbe26a1088877bb` |
| Core | `6afb105c47da8976c9d61e5ea79c7ca6b1d960a6` |
| Scheduler | `bc62f6d5e927557354959b9f051ea21c8457d0f6` |
| Inbox/actions | `cc84d698911660280239a120ae679e473d882f6d` |
| UI | `ff2d4ddb716ad5a2902edc8df6b7f74bce02a843` |
| Joined | `216b2eabfd25b6467d64e97906601879ad723084` |
| Paused manual WIP | `d10874b5e56eb6f0ada98d11fca22eac1c6fd22b` |

The full [source register](reminders-s3-scope-review-evidence/source-register.json)
preserves all 36 old exact resume refs and visible-version mappings. All 36
resolve; 26 change IDs are visible and ten are hidden-only/hash-only. The old
archive rebase note is not today's source register. The requested
`exactinventory.tsv` is actually retained as
[`inventory.tsv`](jj-history-review-evidence/inventory.tsv); no evidence loss
is inferred from the different name. No source alternative is discarded.
[Reviewed-version comparisons](reminders-s3-scope-review-evidence/reviewed-version-comparisons.json)
confirm the named historical scheduler, UI and joined review sources differ
from their inspected visible versions only in historical docs/plans, not code
or tests. Their review limits still apply. The [scout disposition](reminders-s3-scope-review-evidence/scout-disposition.md)
explains why the main proposal rejects optional restore safety and broad P2
reactivation suggested in the raw archive analysis.

| Component | Exact source | Implemented | Review evidence | Test evidence | Current-baseline fit | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| Identity, policies, time resolver and preview | Accepted: `src/reminders/{identity,policies,rules,zoned_time,preview}.py`, `src/api/reminders.py` | Yes: private storage/API and pure preview, **not delivery** | Accepted S2/P2 records; historical reviews, not new code approval here | Accepted records inherited; actual source inspected here | Best starting point. `rules.py`, `zoned_time.py` and reminder API match Joined bytes. Keep accepted P2 boundary. | **Reuse accepted source.** Add only small opt-in/claim semantics later. |
| Durable events, day identity, watermark, claims and retention | Joined: `src/reminders/storage.py`, schema additions in `src/database_setup.py` | Yes, broad repository with many later contracts | Storage reviews and later component reviews; not a review of an A-sized extraction | Fresh selected claim/generation/restore/scheduler run: 150 total. Not all storage tests run here. | Accepted schema ends at 18; Joined runtime spans 19–28 and adds many coupled proof tables. | **Reuse invariants and test cases; rebuild a small daily record/claim.** Do not copy the whole storage module. |
| Daily summary generation and live membership | Core/Joined: `generation.py`, `evaluator.py`, `dispatch_preparation.py` | Yes, with rules, quiet, repeats and later cooldown dependencies | Internal core/scheduler reviews and later component joins; scope limited | Fresh generation module included in 150; inherited larger component gates separate | Archived generation imports public `preview.quiet_end`; Accepted has `_quiet_end`. Other policy/lifecycle seams differ. No foreground-only A implementation exists. | Reuse summary eligibility/time ideas; **write the narrow foreground flow on Accepted**, not an old engine transplant. |
| Non-sending scheduler | Scheduler: `scheduler.py`, `server.py`; Joined adds more preparation | Yes, supervised minute scan and recovery | [Scoped scheduler review](reminders-s3-scope-review-evidence/inherited-reviews/scheduler-review.md) approved status recovery, not dispatch/full S3 | Fresh scheduler module included in 150; historical 138+5+1 review checks inherited | No scheduler in Accepted. Later actual restore-lock changes are on the manual line, outside the fresh snapshot check. | **Not needed for A.** Candidate for B only after exact-version and final-claim review. |
| External restore state and claim guard | Joined: `restore_state.py`, `runtime_guard.py`, strip/API claim paths | Helper and protected paths exist; not a complete A integration | S5 foundation and S3 protected-path reviews inherited; scheduler snapshot alone is not a final fence | Fresh restore module included in 150; current A seam does not exist to test | Atomic external state can inform A, but missing/corrupt-state handling and actual held-lock/cutoff semantics need new seam tests. | Selective helper reuse is reasonable; **review the actual claim/restore integration anew**. No production config change now. |
| Inbox/read/dismiss API | Inbox/actions: `src/api/reminder_inbox.py`; Joined includes later strip/snooze contracts | Yes, private paged events/actions; no manual-now endpoint | Archived component records, not full release approval | Actual source/tests inspected; API suite not freshly run in Task 5 | Requires new records/migrations and changed lifecycle/epochs. It exposes more event states than A needs. | Reuse authorization, ownership, stale-action and paging patterns; **build only recent daily records and dismissal**. |
| History/strip UI and private-context fencing | UI/Joined: reminder history/strip/context modules, DueCenter and settings integration | Yes, on the parked runtime line | [Whole UI review](reminders-s3-scope-review-evidence/inherited-reviews/ui-review.md): scoped approval with signal-first privacy limits | Inherited 73 unit/90 browser/3 external checks in review; Joined report has 300 focused browser cases. **No fresh browser run here.** | Old combined source lacks P2's false flag; settings and private data signals differ. Early polish merge had 387 passes plus a WebKit teardown error. | Reuse lessons/tests, not full old UI. Adapt a small prompt/recent-record view; preserve privacy limitations and obtain new browser review. |
| Snooze, repeat, frequency/cooldown, fallback and manual work | Exact refs and paths in [archive analysis](reminders-s3-scope-review-evidence/archive-analysis.md) and source register | Mixed: several advanced components exist; summary snooze/fallback integration/manual runtime remain incomplete | Component-specific approvals only. Manual WIP is explicitly unreviewed; its appended helper was uncalled/untested. | Broad historical claims remain inherited; no advanced matrix repeated | Coupled to migrations 24–29/proof/lifecycle work. Manual schema 29 was unregistered and dispatch remained fenced at pause. | **Outside A.** Preserve all source/probes. Neither a source count nor an old pass justifies revival. |

### Protected alternatives and recovery limits

- Scheduler change `qnuqpxvz` has exact alternatives
  `22ee5525fea92dbfe885cd123ff3d92f556893c6` and
  `31077a91123572b05e77baa41be804c6347967bb`. Source/tests differ; the latter
  has a runtime-doc conflict and fewer tests. Neither was selected or rewritten.
- API change `oltznxqw` has alternatives
  `c5ce1c843766b0a85d3020b27321730c730d9514` and
  `d8e8f9946cce76c82c06ad6c2533cc213a42ca2c`. Their difference is docs only,
  not proof that either recovery reference may be removed.
- Keep the early P merge conflict `53f76283d923e59084bcd109d400797e8aa78dcb`,
  scheduler conflict above, and identity merge conflict
  `6addc91115e22a0e8ce7b0c33486d9c0b7bd2e0c`. The identity conflict is not a
  clean current integration base. Keep its parents and both identity contracts.
- Manual WIP is not a preview candidate. No cherry-pick, merge, rebase,
  conflict resolution, abandon, rename, cleanup or garbage collection of any
  parked line was performed. Review conclusions do not release these sources.

## Reuse versus rebuild

A full recovery would bring substantial behavior A excludes. The selected
reminder seam between Accepted and Joined changes **51 files, +11,503/-260
lines, including tests**. That is a scope warning, not an effort estimate or
an argument that existing work is bad.

**For A:** keep accepted identity, authorization, confirmed time and due views.
Reuse well-inspected pure helpers where their contracts match. Port the high-value
negative tests and durable identity/claim/restore patterns. Rebuild only the
small daily state, private route and UI. A smaller codebase still needs full
security review; “rewrite” does not mean “skip the hard checks.” Do not renumber
or import old migrations as a shortcut.

**For B:** selective recovery becomes more attractive because generation,
cancellation, claims and scheduling are genuinely needed. First freeze exact
versions, reconcile accepted identity/policy/clock contracts, and account for
P2/polish and restore fences. Test the new combined state. The fresh historical
passes reduce uncertainty about recoverability, not that integration cost.

**For C:** leave the app and archives as they are. There is no benefit from a
cleanup or partial settings exposure. No sunk-cost argument requires shipping
code that five users do not need.

## P2 exposure, S4 and S5

A does **not** turn on `PERSONAL_REMINDER_SETTINGS_ENABLED` globally. A later
approved brief must define a separate limited daily-brief entry and capability
boundary. The server must not start executing hidden custom/scheduled rules.
Preserve saved advanced values; show an explicit unsupported/disabled state if
an existing policy cannot be honored, rather than silently replacing it.

Before any limited setup is exposed:

- Use plain text: **On this device**, **Daily brief**, **Off**, **Pause**,
  timezone and next eligible time. No “policy”, “enrollment” or “phase”. No
  phone permission/status controls suggesting push exists.
- Show “Reminders are off on this device” with one explicit enable action.
  **Try again** appears only after an actual failure, not missing setup.
- Keep the add bar clear; use named compact icon actions where an item action
  is actually included. A does not expose an unused per-item editor simply to
  satisfy an old mockup.
- Inventory the P2 pauses: 102 private-reminder and 18 policy-editor cases
  across three engines. In a full S3 reopening, restore all relevant tests.
  In A's limited reopening, explicitly map each paused behavior: re-enable
  tests for exposed controls and add A-specific tests; retain clear skips for
  truly hidden advanced editors. Never delete assertions or claim 120 cases
  passed merely because the old flag stayed off.
- Run phone-width light/dark, keyboard/focus, error/offline, two-tab privacy and
  public-share checks in Chromium, Firefox and WebKit. Resolve relevant failures
  before exposure. Old WebKit retries do not make a failed full gate green.

**S4 stays on hold.** A deliberately does not provide a durable background
outbox/scheduler or phone transport. Later push needs an approved contract,
reviewed runtime, subscription/security work and its own release approval.
Reuse identity/time/authorization/day dedupe where useful, not a guessed sender
adapter now. B lowers some scheduling rework but does not complete S4. C delays
its prerequisite. None of these options claims physical phone delivery.

**S5 stays on hold as a batch.** A still needs the relevant finish work before
shipping: clear setup/limitations, mobile accessibility, private-state clearing,
recovery behavior and honest diagnostics. It need not build a transport dashboard
or phone provisioning guide for a feature with no phone channel. Future S4/S5
briefs need owner-approved scope updates, not silent reinterpretation.

## Material owner choices

| Choice | Recommended default | Consequence of choosing differently |
| --- | --- | --- |
| Which next release: A, B or C? | **A**, only if a daily prompt while using the app is wanted. This replaces the old full-S3 scope for the next release, not its historical record. | B adds useful at-due prompts but a much larger runtime/test surface. C adds nothing now and avoids new state/UI maintenance; choose it if closed-app prompting is the real goal. |
| May limited in-app settings appear before phone notifications? | **Yes for the selected small scope, after its review/checks.** Keep advanced editors hidden and require fresh explicit activation. | No means A/B cannot be exposed under the current hide-until-phone wording. Keep C/current behavior until the owner changes that gate. It is not permission to turn all P2 settings back on. |

There is no request here for deployment, spending, dependencies, archive cleanup,
real enrollment or a new service. Choosing scope is not approval to implement it.

Ordinary future implementation choices include the names of daily-state tables,
route/component layout, pagination detail and test-fixture layout. The later
agent can choose these within the approved behavior/security contract. The
cookie-doc correction and exposure wording must be agreed explicitly; no code
should be changed just to make the contradictory sentence true.

## Draft small implementation slices and acceptance checks

These are ingredients for a later approved brief, **not another work queue**.
The existing backlog remains the agenda.

1. **Freeze the reduced contract and capability boundary.** Agree exposure and
   update affected current docs/briefs only after approval. Prove S1 counts,
   list/share isolation and P2's advanced controls stay unchanged. Old saved
   enrollment/custom values must not silently turn into live reminders.
2. **Implement daily identity/claim/acknowledgement with fixtures first.** Use
   real current auth and one SQLite transaction. Test nonempty first use,
   same-day no replay, activation after the anchor, DST gap/fold, time/zone
   edits, quiet/cap/spacing, empty rooms, and old-day discard. Race two tabs;
   reopen the DB; prune recent records then retry. Duplicate suppression and
   private ack must survive all three.
3. **Protect final claims, restore and current relevance.** Test two devices
   and two rooms, foreign IDs, public shares, sign-out/password reset/expiry,
   room/item deletion, completion/date change and explicit resume. Exercise a
   real concurrent restore guard across claim/commit, missing/corrupt state,
   SQLite replacement and cutoff equality. Failure must offer nothing and
   leave unrelated data intact; due browsing remains usable.
4. **Add only the small setup, prompt and recent-record UI.** Test first-run
   wording, offered versus dismissed, lost responses/unknown saves, visible
   return, hidden/offline suppression, private invalidation and teardown,
   keyboard/focus and 390 px light/dark layouts. Restore coverage for exposed
   P2 controls. Then obtain fresh whole-combination review and normal affected
   Python/frontend/browser gates. No provider/phone test or service change is
   implied by these slices.

## Checks, review and closeout

- Fresh historical check: **150 passed, 18.18 s, exit 0** on exact Joined source;
  source unchanged. [Command, environment and limits](reminders-s3-scope-review-evidence/research-checks.md).
  This is not current compatibility or a new feature test.
- Fresh independent report/source review: **PASS**, no material blockers.
  [Exact reviewed result, checks and limits](reminders-s3-scope-review-evidence/final-independent-review.md).
- Separate Lead-requested checks of this combined overnight entry: **1,792
  Python tests**; frontend lint/types/build; **1,115 unit tests each in UTC and
  Europe/Oslo**; Ruff and Python types all passed. Imported/configured roots
  and 372 unchanged source/test/config hashes were verified. These checks are
  **not S3 evidence** and do not clear Task1's browser failures.
- No full browser matrix, phone test, product repair, real notification,
  settings activation or persistent app service. The current suite used only
  fixtures, including its temporary server/database shutdown test.
- Docs build passed with the same 51 warning count as Task4. This background
  report is excluded from that build; its source links are checked separately.
  [Commands, first failures, review follow-up and cleanup](reminders-s3-scope-review-evidence/closeout.md).
- Protection baseline: [state](reminders-s3-scope-review-evidence/protection-before.json),
  [all archive file hashes](reminders-s3-scope-review-evidence/archive-before.tsv),
  [60 exact source fingerprints](reminders-s3-scope-review-evidence/protected-source-fingerprints.json).
- [Ownership and frozen sources](reminders-s3-scope-review-evidence/ownership.md).
  The disposable historical snapshot was removed after logs were retained.
  The Lead-managed entry and interactive Conductor remain. No earlier task
  result or existing bookmark was moved.

**Completion means the owner can choose scope from this report. It does not
mean S3 exists, its settings are exposed, or implementation is authorized.**
