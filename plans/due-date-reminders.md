# Configurable due-date reminders

Lifecycle: tracked

**Status: approved for implementation; in progress.** On 2026-11-03 the owner
selected **A/A/A** and explicitly authorized the Lead to deliver all five
stages through one Conductor per stage, with subagents. This includes the
planned scheduler, schema/timezone changes, `pywebpush`/VAPID and worker
extension. Routine implementation assumptions are delegated to the Lead.
Feature acceptance, moving `main`, deployment, extra spending and real-device
notification enrollment remain unapproved. The owner will review before live
release.

Current behavior: [due-date reminders](../docs/due-date-reminders.md).
Evidence and external sources: [research report](../docs/background/reminder-redesign-research.md).
Approval and delivery safeguards: [scope](../docs/scope.md).

## Recommended outcome

A quiet list app with a capable reminder system behind it:

- A bell opens due items for the room or current list. Counts and date labels
  remain visible without interrupting editing.
- Configure several reminders, such as a week before, a day before and at the
  due time. Use presets first; reveal custom controls on request.
- Choose a daily summary, scheduled reminders, both, or neither. Snooze and
  dismiss without changing anybody else's due date.
- Opt into phone notifications on supported devices. Without permission or
  support, the due overview and in-app reminders still work.
- Keep the present Svelte/FastAPI/SQLite stack, one service and no accounts.
  Add a durable scheduler and standards-based Web Push only with approval.

This is not a proposal to remain limited to the present two simple toasts.
It is also not a request to copy every feature of a full task manager.

## Boundaries and ownership

- **Home** means the room overview at `/room/{slug}`, not a new cross-room
  dashboard at `/`. Reminders never reveal other rooms.
- Shared item dates and optional due times are shared facts. Reminder rules,
  channels, quiet hours, notification history and snoozes belong to this
  browser/app installation. Say **On this device**, not **Your account**.
- One installation can opt into several authorized rooms. A browser and its
  separately installed app can be separate installations. There is no
  cross-device preference or snooze sync without a later identity design.
- Anyone may view due items within their existing access. A public share link
  stays list-scoped and cannot enroll in scheduled or push reminders. Room
  sign-in is required; installation alone grants nothing.
- No accounts, assignments, recurring-task engine, location reminders, email,
  SMS, native app or critical alarms in this delivery. These are not hidden
  prerequisites for the requested feature.
- The owner selected this delivery as current work. The
  [backlog](backlog.md#current-focus) links here; parked `groups` stays untouched.

## Recorded owner choices

**A/A/A selected, with explicit implementation approval (2026-11-03).** The
alternatives remain product settings, not unresolved questions. A means daily
09:00 summary, generic/private phone text and all five delivery stages.

| Choice | A — recommended | B | C |
| --- | --- | --- | --- |
| 1. Default reminder mode | One daily summary at 09:00; no individual alerts until selected | Scheduled: one calendar day before and at the due anchor | Quiet: counts and due overview only |
| 2. Default phone text | Generic: “You have reminders. Open ListR.” | Counts, without names | Item/list names visible on the lock screen |
| 3. Planned delivery endpoint | All five stages, including the proposed scheduler, dependency and Web Push architecture | Stages 1–3: full in-app scheduling, no phone push yet | Stage 1 only: quiet due overview first |

All reminder modes and message-detail levels remain configurable regardless
of the chosen defaults. Stage 1 deliberately has no automatic warning; the
chosen default starts with the scheduler in stage 3. Phone push is always off
until the person enables it on that device.

The owner's implementation approval covers the supervised FastAPI scheduler,
new SQLite migrations, optional shared due-time fields, `pywebpush`/VAPID,
IANA timezone data (`tzdata` if needed) and the existing service-worker
extension. No additional service or spending increase is approved. The Lead
may integrate reviewed child results into its isolated delivery line under
the shared role contract. Moving feature work to `integration` and deploying
remain owner gates; docs-desk commits normally retain their standing permission,
subject to the current bookmark hold recorded below.

### Delivery coordination

- Lead: Pi session `01a1aa7e-4659-74d2-b51e-a2fb367fdeec` (from 2026-11-05;
  earlier `01a1a2c7-22c9-71e2-897a-af8ac7de162d`).
- Aggregate workspace: `tmp-reminder-delivery`,
  `/home/hsa/projects/tmp-reminder-delivery` (Lead-created/managed).
- Five ordered delivery stage briefs: [S1](batches/reminders-s1.md),
  [S2](batches/reminders-s2.md), [S3](batches/reminders-s3.md),
  [S4](batches/reminders-s4.md), [S5](batches/reminders-s5.md).
- Conductors: GPT-6.1 Sol, initially low for S1/S5, high for hard work including
  S2–S4 and S1's expanded lifecycle diagnosis. Verify effective
  model/thinking before granting edits. Owner's latest 2026-11-04 instruction:
  checkpoint and stop active Sol subagents promptly, then use
  `openai/gpt-6.1-terra:medium` for **all implementation and independent-review
  subagents**. Conductors remain unchanged. This replaces the earlier Sol
  fallback and Haiku defaults for this delivery. Do not automatically escalate
  to Sol/high. Preserve handoffs and stop the old writer before replacement.
  Verify effective provider/model/medium; report unsupported settings rather
  than substituting. Claude remains unavailable due to quota.
- Overnight continuation (owner request, 2026-11-04): continue coordinating
  approved delivery for up to eight hours or completion, aiming for a reviewed,
  verified local preview for the owner's morning inspection. Keep ready work
  moving through real predecessor handoffs; preserve/report genuine blockers.
  This does not approve release, bookmark moves, real push sends or extra
  spending. Use existing completion notifications; no reminder/scheduler tool
  is exposed in the current harness.
- Lead alone writes the backlog, this plan and the owner-review list below.
  Each Conductor owns only its separate batch record's status/closeout; shared
  records are edited/committed on the docs desk with coordinated write windows.
- Owner relay on 2026-11-04: continue authorized isolated integration, verification
  and creator cleanup; keep `integration` and `main` fixed, including docs-only
  bookmark advancement, unless separately authorized. Docs-desk records may be
  committed above the held bookmark; do not mistake them for feature acceptance.
- Owner review pending: final implementation/UX; feature acceptance; deploy;
  actual push provisioning/phone opt-in. No production configuration or real
  external push will be changed/sent during automated implementation.
- Owner decision pending: where to place separate frontend tooling maintenance
  in the backlog (recommend Later). [Audit triage](../docs/background/reminder-delivery-verification.md#existing-frontend-tooling-audit)
  found existing dev/test risks, not identified production reachability. No
  upgrades or new reminder release gate are approved; backlog placement needs
  the owner's decision, not an automatic queue addition.
- **Run of 2026-11-05 (Lead Pi `01a1aa7e`, owner away ~9 h).** Order:
  [polish P](batches/reminders-polish.md) and S3 run in parallel (P is
  frontend-only on reviewed S2; S3 is mostly server work), then S4, then S5,
  each started only on its reviewed predecessor. Conductors are visible Pi
  peers named `reminders-<stage>-list-app` on GPT-6.1 Sol/medium (owner
  choice, replacing low/high for this run). All implementation and review
  subagents stay `openai/gpt-6.1-terra:medium`. Lead integrates P, then S3,
  S4, S5 into `tmp-reminder-delivery` and refreshes the local preview. Same
  limits: no deployment, held-bookmark moves, real pushes or extra spending.
  S3 successor Conductor takes over the closed S3 Conductor's workspaces.
- Lead's combined checks and review evidence:
  [delivery verification](../docs/background/reminder-delivery-verification.md).

## Approved product contract

The numbers below are approved product defaults, not claimed industry standards.

### 1. Always-available due information

- Room bell: all unchecked dated items in that room, with list names.
  List bell: that list only, with no room-scope switch (owner polish
  2026-11-05). A share page cannot expand its scope.
- Group into **Overdue**, **Today**, **Tomorrow**, **Next 7 days** and
  **Later**. The last two groups are disjoint: Next 7 days means days 2–7
  after today; Later is beyond day 7. All dated items remain discoverable.
- The badge counts unchecked items overdue or due today/tomorrow, not unread
  messages or the number of reminder rules. Opening the bell does not clear
  that count. Zero has no badge; large counts may show `99+` with a full
  accessible label. A list card shows the same list-specific due count.
- A due item appears once even with several reminder times. Sort by due
  day/instant, then list/name and UID for deterministic ties. Completed and
  undated items are excluded. Existing tag/search/hide-done filters do not
  silently remove items from this whole-list overview.
- Date labels: red + “Overdue”; amber + “Today”/“Tomorrow”; neutral for later.
  Use existing theme tokens, with tested contrast in every light/dark theme.
  No continuous gradient or whole-row urgency wash. Keep the actual date and
  optional time readable; color is never the only signal.
- Tap an item to open its list and reveal/focus that item, clearing conflicting
  filters explicitly. A deleted/inaccessible target gives a clear unavailable
  state, never another room's content. Do not steal focus on live updates.
- The panel works from saved offline data and labels it as such. Recompute on
  visible-page return, live/offline edits and local day rollover, not only on
  navigation. A sleeping tab catches up when visible.

### 2. Settings without a wall of controls

- Put **Reminders** in the room menu and in the bell panel's settings action.
  The primary screen shows mode, summary time, phone status and timezone.
  Due information needs no enrollment. **Enable reminders on this device**
  explicitly saves the initial room enrollment and selected mode; merely
  opening a room never subscribes it. Phone permission is a separate action.
  Device-wide controls are visibly marked as affecting all enrolled rooms.
- Presets: **Quiet**, **Daily summary**, **Scheduled**, **Custom**. Scheduled
  starts with one day before and at the anchor. Choosing Custom exposes
  **Add reminder**, quiet hours, limits, overdue repeats and content privacy.
- In the item dialog, keep **Date** simple. Add optional **Time** and one
  **Reminders: Uses list settings** row. That row opens the same editor used
  elsewhere, with an inheritance summary and next-run preview. It must not
  require walking through several nested settings dialogs.
- Rule precedence on this device: item override > list override > device's
  room default. An override replaces the inherited rule set; it does not add
  to it. Explicit Off differs from Inherit. Reset restores inheritance.
  Device-wide pause, room opt-out, quiet hours and safety limits always win.
- Support up to **five effective reminder rules per item**, including optional
  fixed date/time reminders. Preset offsets include 7 days, 1 day and at due;
  Custom supports integer minutes/hours/days/weeks before the anchor, up to
  365 days. Reject invalid/past fixed times, duplicate equivalent rules and
  oversized input; coalesce distinct rules resolving to the same instant.
- A fixed reminder is personal and independent of the shared due time.
  Moving the due date moves relative reminders, not a still-future fixed
  reminder. Removing the date cancels all its reminders. Label this distinction
  in the preview rather than silently moving an absolute time.
- Show the next actual reminder times, timezone, inheritance source and any
  quiet-hour adjustment before Save. Changing defaults affects only inheriting
  items/lists. Editing the shared date/time uses the existing shared Save flow;
  saving personal rules is a separate explicit action and cannot falsely claim
  an atomic save of both shared and personal data.

### 3. Date, time and timezone rules

- Preserve `date: YYYY-MM-DD | null`. Existing date-only items remain date-only;
  never migrate them to midnight deadlines. A date-only item is overdue only
  when its calendar day has passed.
- Add optional shared `due_time: HH:MM` and `due_timezone: IANA zone`. Both are
  required together and need a date. The item editor starts with this device's
  configured zone, displays it, and saves it explicitly. A timed item is
  overdue after its due instant, even if that instant was earlier today.
- A date-only item's reminder anchor is its date at the device's all-day
  reminder time, initially 09:00 in its configured zone. This is a reminder
  time, not a newly invented due deadline. A timed item's anchor is its shared
  due date/time/zone. Fixed personal times carry their own explicit zone.
- Store and publish read-only `due_at` (UTC) for timed items, resolved by the
  server from date/time/zone; null for date-only items. Recompute it atomically
  whenever any source field changes. Clients send date/time/zone only; reject
  a client-supplied `due_at`. Those wall-clock fields preserve intent; stored
  `due_at` is the authoritative resolved instant for this due cycle. The
  frontend uses it instead of inventing a second DST resolver. Offline
  due-time drafts show their wall time and **Waiting to sync**; do not present
  an unconfirmed draft as a newly server-scheduled instant. Timed at-due and
  minute/hour offsets use the stored confirmed `due_at` directly, even if zone
  data later changes; calendar-day/week offsets use wall intent and the common
  resolver. Do not silently re-resolve an unchanged timed anchor.
- Store UTC instants for work/delivery, IANA zones and wall-clock intentions for
  recalculation. New setup defaults to Europe/Oslo (owner polish 2026-11-05),
  not the browser zone; do not use a fixed UTC offset. Existing saved zones
  stay as they are. If it changes, offer an explicit timezone update with a preview;
  do not silently reschedule while the app is closed.
- For date-only items, buckets use the configured device zone (Europe/Oslo
  before setup). Timed items use their instant for overdue status and the
  device zone for Today/Tomorrow grouping. Display the zone if it differs from
  the current browser zone. A timezone change recomputes future work only.
- Days/weeks subtract calendar days in the anchor's zone at the same local
  clock time; hours/minutes subtract elapsed time from the resolved instant.
  Around DST gaps use the first valid local instant after the gap; for a
  repeated local time use the first occurrence. Resolve this on the server
  with `zoneinfo`; the preview and scheduler must use that same resolver.
  Include production-image IANA-zone availability in the approved dependency
  decision: verify it in image checks and add Python `tzdata` through `uv` if
  needed. Missing zone data must visibly disable affected reminder processing,
  not silently fall back to UTC or make the whole list app unusable.
- Clearing the date atomically clears its shared time/zone. Clearing only the
  time returns to a date-only item. Old offline operations with absent new
  fields keep them unless the date is cleared; explicit null clears them.
  Extend restore/undo, snapshots, validation and field-conflict handling too.

### 4. Reminding, quiet hours and frequency

- Daily summary: one per enrolled room/device/local day, at the chosen time,
  including unchecked overdue/today/tomorrow items. Skip empty summaries.
  Scheduled mode uses the selected rules. Custom can combine both explicitly.
- The in-app bell panel has **Due items** and **Reminders** views. Due items
  are live facts; Reminders is a persistent, paged event history with pending,
  snoozed, dismissed and transport states. Reading an event does not complete
  the item or remove its due badge.
- No list-open warning and no five-minute room toast. New in-app reminders
  can produce one non-modal, dismissible summary strip; the content remains
  in Reminders. It never blocks the add bar or grabs focus. One strip at a
  time, with due events grouped by room. Optional disabling leaves counts and
  history intact. No auto-disappearing action is the sole way to snooze.
- Device-wide default quiet hours: **22:00–08:00**, configurable or off.
  Default maximum: **10 interruptive notifications/day**, adjustable 1–50.
  Default minimum spacing: **10 minutes**, adjustable 1–60. Apply these to
  combined automatic in-app/push dispatches, not bell browsing or history.
  Count by the configured device timezone's dispatch day; the OS may display
  accepted push later. Reserve quota and spacing durably before dispatch,
  across tabs and rooms.
- Group events in the same room becoming eligible in the same minute into one
  notification. Never combine private names across rooms. During quiet hours,
  hold eligible work and emit one current room summary at quiet-hours end,
  subject to device spacing. Do not replay one alert per missed rule.
- During cooldown, coalesce waiting work until the next allowed time. After
  the daily cap, retain events in history and the next daily summary, not a
  midnight backlog burst. A daily summary replaces matching pending individual
  interruptions for items it covers, without canceling future rule times.
- Optional overdue repeat: off by default; once per local day at the summary
  time, for at most seven overdue days (configurable 1–30). Day 1 is the first
  device-local summary anchor strictly after a timed item's confirmed due
  instant, or the first local day after a date-only item's date. Count consecutive
  summary days from that due-derived anchor, not sends or enrollment; pauses,
  caps and missed days do not extend the window. Quiet deferral does not renumber
  a repeat day. Future-only activation still prevents backfill, and summary-time
  or zone edits cannot replay past days or duplicate a local day's repeat.
  If the daily summary already covers it, do not add another interruptive repeat.
  Counts persist after repeats stop. Quiet hours may cross a date boundary.
- On enrolling or changing rules, show future reminders. Do not replay every
  offset already passed. Offer **Remind me now** for an already-due item as an
  explicit action for one already-due item, still subject to quiet hours and
  the shared frequency cap. It cannot override Quiet mode, effective Off,
  pause, opt-out, invalid authorization or an active current-cycle snooze.
  Explain the blocked state; never clear or shorten snooze implicitly or add
  a second wake. Date-only today qualifies even before its reminder anchor;
  tomorrow does not. Timed items qualify at or after confirmed `due_at`,
  including equality. Quiet hours can defer an otherwise valid manual reminder.
- Same-day retries reuse the interruption's quota and spacing reservation;
  they do not consume another slot that day. A retry crossing a local day
  boundary must reserve a slot in the new day before sending; retain any
  attempted old-day charge, and reuse the new slot for later same-day retries.
  On cancellation/expiry, release quota only if no send was attempted and
  delivery is provably absent. Ambiguous attempts still count; never rewind
  the spacing clock. Once an occurrence is grouped into an interruption,
  reconciliation cannot regroup it into another pending send.
- After an outage, pending scheduled alerts up to one hour late can be grouped
  once if still relevant. Older ones remain in history/next summary. A missed
  daily summary may catch up once during that same local day; older daily
  summaries never replay. Quiet-hour deferral is intentional, not an outage.

### 5. Snooze, dismiss and cancellation

- Snooze choices: 15 minutes, 1 hour, tomorrow at the all-day reminder time,
  or a custom future date/time (up to 365 days). Preview quiet-hour adjustment.
- Snooze suppresses all interruptions for this item's current due cycle on
  this device until that instant, replacing any previous snooze. Wake with
  one reminder if it is still eligible; coalesce any rule at the same instant.
  Snoozing the daily summary instead snoozes that summary occurrence, not
  every item's future rule. Label the scope in the action.
- Dismiss acknowledges the occurrence only. It does not change the due date,
  complete the item, disable future rules or dismiss other devices' reminders.
  **Stop reminders for this item** is a separate personal override.
- Completing/deleting an item or removing its date cancels unsent work and
  snoozes. Changing due date/time/zone starts a new due cycle and cancels the
  old cycle's pending relative work/snooze; still-future fixed reminders keep
  their stable rule/instant identity and do not become duplicate occurrences.
  Completing an item cancels pending fixed reminders too. On unchecking,
  reactivate only still-future, never-attempted fixed reminders; never resend
  an accepted or past fixed reminder. Unchecking starts a new relative due
  cycle with future rules only, not a burst of already-missed alerts.
- Renaming, quantity or tag edits do not restart a reminder cycle. Viewing or
  dismissing a notification does not imply the underlying task is done.
- Notification tap opens the app; snooze works inside it everywhere. Optional
  platform action buttons may deep-link to an in-app snooze choice. Do not
  depend on lock-screen buttons or grant shared write authority to a payload.

### 6. Offline and synchronization limits

- Keep viewing due items and editing shared date/time through the existing
  offline queue. Schedule only server-confirmed state; queued phone edits may
  temporarily disagree with server reminders. Show **Waiting to sync**.
- Personal preference changes, enrollment and reminder actions require a
  connection in this delivery. Keep drafts and clearly disable saving offline;
  do not create another offline write queue as a hidden dependency.
- Local read state may be cached. Reminders cannot claim to be server-snoozed
  until acknowledged. No exact closed-app reminder from a page timer.
- An offline sign-out can stop local UI but cannot immediately revoke a server
  enrollment. Try the existing pending sign-out flow and display that phone
  reminders may continue until the server confirms. Generic text limits
  disclosure; do not promise immediate remote revocation without connectivity.

## Worked acceptance examples

Use these as end-to-end fixtures, in addition to the edge-case tests per stage.

| Scenario | Expected result |
| --- | --- |
| Date-only item due 10 November; 7-day/1-day/at-due rules; 09:00 Europe/Oslo | Reminder anchors are 3, 9 and 10 November at 09:00 Oslo time; the due date stays date-only. |
| Enable that schedule on 3 November at 10:00 | No replay of the missed 09:00 warning; preview starts with 9 November. |
| Two tabs navigate through the same list repeatedly | Due counts update; no navigation warning and no duplicate claimed in-app strip. |
| Two people use separate devices; one snoozes an item | Only that installation's current item cycle is snoozed; shared date and the other device are unchanged. |
| A reminder is due at 23:00 with 22:00–08:00 quiet hours | It contributes to one current room summary after 08:00, not a burst of every deferred event. |
| The item is completed before that deferred send | Recheck removes it; if nothing eligible remains, no notification. |
| Date-only reminder lands in Oslo's 29 March 2026 02:30 DST gap | Preview and scheduler both resolve to the first valid time, 03:00. |
| Push provider accepts, then the server crashes before recording success | Recovery uses the same stable IDs/tags and reservation; a rare repeated delivery remains possible and is not reported as exactly once. |
| Room password is reset while every page is closed | Saved authorization no longer validates; no new send for that enrollment. An already-accepted provider message cannot be recalled. |

## Proposed implementation architecture

This design is approved for implementation, but is not a statement that the
current app already has these components. Update current architecture docs
with each implemented stage.

### Personal identity and access

- Create a random, server-issued installation secret in a Secure, HttpOnly,
  host-only device cookie (`__Host-` on HTTPS), `SameSite=Lax`, `Path=/`, no
  Domain, one-year lifetime; store only its hash. Set/renew it only through
  explicit enrollment/resume, not background reads. Match the existing
  plain-HTTP local-test convention. Persist the installation's UTC expiry on
  the server as well; cookie Max-Age alone cannot bound background authority.
  Never expose room tokens to JS.
- Each device/room enrollment records the authenticating room-token hash and
  room authorization version. Existing room cookie + device cookie are both
  required to read/change that device's room reminder data. The device cookie
  alone grants no room access. Lists/items must belong to that room.
- A fresh successful sign-in may explicitly rebind this device's enrollment
  to the new room token after access is revalidated, preserving personal rules.
  Password reset/sign-out disables affected enrollment; re-sign-in requires an
  explicit resume action rather than silently restoring background pushes.
- At generation and immediately before dispatch, revalidate the saved grant
  against live room tokens/version and room/list/item existence. Room deletion
  or password reset cancels unsent sends even without a page open. Persist a
  saved-grant expiry bounded by installation expiry and the original room-token
  issuance time plus the existing room-cookie lifetime; enrolling later cannot
  extend that original background deadline. Explicit fresh sign-in/resume can
  rebind it. GET/validation never renews it. This adds a background-grant bound,
  not a change to existing room API token-validation semantics.
- Keep personal policies/history out of shared room feeds, share-link feeds
  and SSE payloads. Own-device refresh signals must not expose another
  installation's settings. No arbitrary device-ID lookup API. Do not add an
  admin view of personal histories/settings. The server operator can inspect
  the database; do not claim privacy from that operator.

### Storage and API seams

Use the current migration runner and same-origin JSON protections. Suggested
new modules are `src/reminders/` and `src/api/reminders.py`; keep item mutations
in the established API/CRUD boundary.

Minimum logical records (final table names can differ):

| Record | Key purpose |
| --- | --- |
| Installation | Hashed device secret; timezone, quiet hours, caps, pause and content privacy |
| Enrollment | Device + room; authorizing grant/version; active state and selected channels |
| Policy | Enrollment + room/list/item scope; revision; inherited/off/custom rule set |
| Item due cycle | Server UUID plus UTC cycle-start time for date/time/zone changes or done→active, not arbitrary edits |
| Occurrence | Relative: enrollment + item/cycle + normalized rule + scheduled UTC instant; fixed: enrollment + item + stable fixed-rule/instant identity, independent of due cycle |
| Snooze/summary | Item-cycle or summary scope; wake instant; unique summary local-day key |
| Delivery outbox | Occurrence/group + channel; state, lease, retry/expiry and provider acceptance |
| Push subscription | Installation-owned endpoint/keys; unique endpoint hash, active state and key version |

Persist server-only `items.due_cycle_started_at` with its UUID. Sample one
injected UTC clock under the write lock on an actual schedule change or new
dated active cycle (including restore/uncheck); preserve it on unrelated edits,
no-ops and retries, and clear it with the date/cycle. Initial migration backfill
uses one explicit UTC migration instant; it is not historical enrollment.
Relative activation is bounded by the latest of cycle start, enrollment/resume
activation and applicable policy activations. First-seen tick time or arbitrary
`changed_seq` edits cannot substitute for these durable cutoffs. Keep fixed-rule
identity/activation independent. Test the 10:00 cycle change / 10:05 future rule /
10:30 catch-up with a 10:10 rename, and suppress a pre-change 09:55 rule.
Do not accept client cycle/cutoff fields or publish them in shared feeds.

Do not duplicate the whole shared item into every event. Render authorized
history against current data, marking obsolete/deleted occurrences unavailable.
Retain terminal history/delivery records for 30 days; never prune pending,
leased, snoozed or deferred work merely because it is old. Advance a durable
processed-through watermark per enrollment only in the transaction that
records every event or suppression in that interval. Ordinary evaluation
never recreates past work at/before that watermark; policy changes activate
future work, never rewind it. Prune terminal records only when both their
retention age and the processed-through watermark allow it; retain any rule/
cycle dedupe state still needed. Disabled orphan installations/subscriptions
may be pruned after 90 days of
inactivity. Cascades must not delete other devices or rooms.

API under `/api/v1/rooms/{slug}/reminders`:

- `POST /enrollment`: initialize own installation/enrollment or explicitly
  resume after authorized sign-in. Never enroll silently on page load.
- `GET/PATCH /preferences`: own device/room settings; list/item overrides
  through scoped subresources. Return effective source and revision.
- `POST /preview`: compute the draft's next five reminder instants using the
  same pure evaluator as dispatch; validate ownership without saving a policy.
- `GET /inbox`: own paged occurrences; `POST /occurrences/{id}/actions` for
  dismiss/read/snooze. Reject another installation's occurrence ID uniformly.
- `PUT/DELETE /push`: register this installation's subscription and enable or
  disable this room's push channel. One worker subscription can serve several
  rooms; turning off one room must not unsubscribe the others.
- A device-wide **Stop all phone notifications** action revokes all of this
  installation's push channels/subscription. It grants no ability to read
  rooms whose authorization has expired.

Personal mutations use revision checks and an idempotency key scoped to the
installation/enrollment, not the public/shared op-result namespace. Cross-tab
conflicts return a refresh-and-review state, not silent last-writer-wins.
Device-wide edits are clearly separated from a room policy update. Draft the
API contract/tests before wiring forms; do not treat these proposed paths as
already existing endpoints.

### Durable scheduling and delivery

- Extend `src/server.py` lifespan with one supervised task, approximately every
  60 seconds, plus startup reconciliation. A fixed minute scan of the small
  app's active recipients and dated items is sufficient; no Celery, Redis,
  APScheduler or second service. Use indexed due/outbox queries and bounded
  batches. Do not promise dispatch at an exact second.
- Verify Railway Serverless/app sleeping is disabled before rollout. Its live
  value is unknown; checking/changing hosting configuration belongs to the
  approved rollout. The process cannot wake itself after Railway sleeps it.
- Keep a pure evaluator for inheritance, time resolution, eligibility,
  cancellation, coalescing and next-run previews. Use an injectable clock.
  Persist evaluation watermarks and occurrence identities, not an in-memory
  Set or a volatile timer per item. Catch up using the product rules above.
  Snooze wakes are explicit future work, not backdated watermark replay.
- Commit generation, quota reservations and delivery claims under the DB lock;
  release it before HTTP. Run synchronous DB/push work in bounded threads,
  never on the async request loop or while holding a transaction across I/O.
  Use a DB lease/unique claim so restart/reconciliation cannot create two
  simultaneous sends. On shutdown, interrupted I/O is ambiguous until lease
  recovery proves otherwise; do not mark it expired or delivered by default.
  Shutdown and lease expiry must be testable.
- Separate event creation from transports. No push enabled: one in-app strip
  for the event, durably claimed across tabs. Push enabled: push is the
  interruptive transport and the app updates history silently. Do not show an
  extra automatic strip merely because provider acceptance is uncertain.
  Explicitly blocked/disabled push falls back to in-app on the next app visit.
- Transport states: pending, claimed, accepted, retry-wait, expired, canceled
  or failed. **Accepted by push service** is not delivered/displayed/read.
  A crash or timeout after sending is ambiguous: exactly-once delivery is not
  achievable. Reuse stable occurrence/group IDs and replacement tags/topics
  for bounded retry dedupe; do not claim network-level exactly-once semantics.
- Retry temporary failures with bounded exponential backoff/jitter until the
  reminder's expiry. Respect `Retry-After` for 429; cap attempts at five.
  HTTP 404/410 disables that endpoint. Authentication/configuration failures
  pause push and expose a safe diagnostic rather than looping rapidly.
- Normal urgency. Push expiry: at most one hour for scheduled/snoozed alerts;
  daily summaries expire at the next local day. Compute the outgoing TTL from
  remaining relevance time, including time already spent in the outbox.
  Before sending, recheck quiet hours, pause, quotas, item state and access.
- Dedicated `REMINDERS_ENABLED` / `PUSH_ENABLED` operational switches can stop
  dispatch without losing due information. Push defaults off unless explicitly
  configured for the approved environment. Configure tests with fake senders;
  starting the development/test server must never notify real devices.

### Phone enrollment, worker and security

- Use standards-based Web Push and a small maintained Python sender such as
  `pywebpush`, installed through `uv` after approval. Keep the VAPID private key
  in deployment secrets, never source, responses or logs. Configure the VAPID
  contact and canonical HTTPS app origin explicitly; the public key/origin may
  appear in public client configuration. Keep keys stable across deploys;
  document rotation and restoring the correct key. Do not create a Firebase
  application merely
  because Chrome's browser-managed push service uses FCM.
- Android: feature-detect HTTPS, notifications, push and the worker; installation
  is not a blanket prerequisite. iPhone/iPad: provide Home Screen instructions,
  then enable from the installed app; baseline support is iOS/iPadOS 16.4+.
  Do not infer support only from an OS/browser name.
- Explain the benefit before an **Enable phone reminders on this device** tap.
  Preserve user activation when calling permission/subscribe: obtain server
  public config and worker readiness beforehand, not through a long async
  chain after the tap. Never request permission on load. Handle unsupported,
  needs-install, default, denied, granted-but-not-subscribed and active states.
- Add an explicit test-notification button after enrollment; one user action,
  rate-limited. Do not send a test merely because the page mounted. Denial
  leaves the app usable and links to instructions, not repeated prompts.
- Extend `frontend/src/service-worker.ts` at `/service-worker.js`; preserve
  caching, offline writes, waiting-version safety and `/sw.js` retirement.
  Do not register another root worker or change app identity/scope.
- Use a visible payload with title/body, an allowlisted same-origin navigation
  target and opaque occurrence/group ID. Prefer the WebKit-described
  declarative JSON envelope with a tested imperative worker fallback, so
  Safari 18.4+ can show fallback content and older browsers still work. The
  worker must not create duplicate displays on declarative-capable browsers.
  Revalidate the current format at implementation; never require 18.4+ merely
  to support the baseline push flow.
- Every received push must display a visible notification, even with an open
  page, malformed/empty payload or a failed authenticated fetch; use a safe
  generic fallback that opens the app root and contains no room data. Treat
  an unrecognized declarative format the same way. Do not fetch room contents
  before showing it and do not use silent push for sync. Notification clicks focus an
  existing matching same-origin app window when possible, otherwise open one;
  normal room authorization still applies before revealing item details.
- Feature-detect icon badging/actions as enhancements only. In-app snooze and
  tap-to-open are mandatory; notification action buttons, sounds, vibration
  and exact timing are not portable guarantees.
- Treat endpoints and encryption keys as secrets. Validate size/key formats,
  HTTPS, no user-info/fragments and approved provider hosts with exact or
  boundary-safe suffix matching. Reject localhost/private/link-local/metadata
  destinations, nonstandard ports and redirects; prevent DNS-rebinding/private
  resolution at send time. Document the maintained provider-host policy rather
  than accepting any client-supplied URL into an HTTP sender. Test SSRF cases.
- Bind a subscription uniquely to its installation; another device cannot
  replace, inspect or delete it merely by sending its ID/endpoint. Limit one
  active subscription per installation, enrollments per installation and
  subscription mutations/test sends to bounded rates. No raw endpoint logging.
- Default generic lock-screen text unless choice 2 changes it. Detailed text
  is explicit opt-in. No password, room/share token or privileged action in a
  payload/URL. Approved canonical origin, never an arbitrary request Host.
  A message already accepted by a provider cannot reliably be recalled after
  completion, sign-out or revocation; explain that limitation.

## Five dependent delivery stages

Build each stage with its own tests and affected documentation. Runtime
integration follows the numbered dependencies. Lead-approved sequencing
refinement (2026-11-04): isolated S2 backend date/time foundations, followed by
server-only identity/policy/preview APIs after reviewed foundation/own-line gates,
and S4 pure push-transport/security foundations may proceed while predecessors
are verified. Further Lead handoffs allow S3's durable storage repository,
S4's installation-owned subscription storage/contracts and S5's external
restore-state helper on reviewed identity/cycle `rwswntvl` / `3eb72704`.
S4 may also implement isolated existing-worker push/click/payload handling
from reviewed full S2 while S3 finishes, with no scheduler/UI/API hookup.
Their batch briefs bound files, real contracts, review and creator-owned cleanup;
no guessed evaluator stubs or shared migration-runner changes. They become
runtime components only after their reviewed predecessors are reconciled.
These lanes do not wire dependent frontend or dispatch paths,
bypass review/full-stage gates or integrate into the aggregate before predecessors. Reconcile
completed, quiescent lines before dependent implementation; never rebase an
active writer merely for graph tidiness. This is a delivery assumption under
the owner's delegated authority, not added scope.
Each stage can contain several small atomic jj changes. Update the affected
architecture/API/current-behavior docs as each approved stage is implemented;
stage 5 reviews completeness, not a delayed first documentation update. Do not
save all tests for stage 5 or introduce an unfinished push UI in stage 1.

### Stage 1 — Quiet due center

**Depends on:** implementation approval for stage 1.
**Unblocks:** stage 2.

- Replace `showDueReminders` list-open/periodic toasts with pure due grouping,
  the bell/panel, list counts and date labels. Reuse the existing room store,
  list navigation, dialog and theme patterns. Keep normal error/undo toasts.
- Main seams: `frontend/src/lib/list/due-reminders.ts`,
  `frontend/src/lib/ui/due-reminder-toasts.svelte.ts`,
  `frontend/src/lib/room/PageShell.svelte`, room/list headers, `RoomLists`,
  `ItemRow` and new reminder UI modules as needed.
- Tests: list/room/share isolation; done/undated exclusion; all groups and
  stable ordering; navigation/reload produces no warning; offline snapshots;
  midnight/visibility refresh; filters/deleted targets; keyboard/focus and
  six themes in both modes. Replace old tests requiring repeated toasts.
- Lead/Conductor agreed verification refinement (2026-11-04): investigate the
  evidenced empty app-shell cache and full-gate focus/offline failures. S1 may
  instrument and minimally repair the existing worker lifecycle/browser harness,
  including the legacy retirement script only if implicated. Keep current cache,
  privacy, update and one-worker contracts; no dependency/browser-install or
  production-environment changes. The exact upstream ephemeral-versus-isolated
  temporary persistent-profile discriminator is authorized; any representative
  storage-fixture repair must retain assertions and prove profile isolation.
  Attribute the writer before fixing, use matched common-test comparisons,
  isolate any proved repair atomically and obtain fresh max diff review/full
  gates. This is ordinary delivery repair, not a new platform or gate.
- **Done:** due information is discoverable without repeated interruptions,
  in all three browser engines; no business API/schema or permission prompt.

### Stage 2 — Personal policies, dates and previews

**Integration depends on:** reviewed stage 1 and the approved identity/schema/time design.
Server-only foundations and identity/policy/preview APIs may proceed in reviewed
milestones under the sequencing refinement above. Frontend and full-stage
integration still await S1; no scheduler/outbox/push is included in this lane.
**Unblocks:** stage 3.

- Add installation/enrollment and policy records/API, shared optional due time
  and timezone, stable due-cycle identity, and pure schedule resolver/preview.
  No outgoing reminders or real subscriptions yet.
- Implement presets, inheritance/reset/off, up to five relative/fixed rules,
  device settings and one reusable editor. Show clearly that scheduling is
  not active until stage 3; avoid enabled controls that imply delivery exists.
- Extend item API models/CRUD, migrations/triggers, undo/restore, feeds, TS
  types, offline overlay/snapshots/queue validation and conflict handling.
  Preserve old queued-op hashes and compatibility; follow
  [API versioning](../docs/api.md#api-version) if the contract requires it.
- Tests: upgrade old DB; absent/null/clear semantics; legacy date-only changes
  keep a timed item's time/zone while date-clear removes them; reject client
  `due_at`; recompute stored UTC; IANA data in the image; all due-cycle
  transitions; defaults/list/item precedence; invalid offsets/duplicates/limits; fixed vs
  relative dates; positive/negative-offset zones, leap days, DST gap/fold,
  month/year rollover; two-tab policy conflict; room/device/share access;
  offline legacy date edits and restore; no send side effects from preview.
- **Done:** a user can see/save an understandable effective schedule, with
  correct timezone previews and no changes to another device's preferences.

### Stage 3 — Durable in-app reminders and snooze

**Depends on:** stage 2 and approval of the scheduler/hosting proposal.
**Unblocks:** stage 4; is the complete delivery endpoint for choice 3B.

Implement in three reviewable internal steps, each with targeted tests:

1. **3a — Durable core:** occurrence/outbox storage, processed-through cursor,
   evaluator, claims/leases and saved-grant cancellation. Fake transport only;
   do not expose a partially protected dispatch path.
2. **3b — Daily summaries:** quiet hours, grouping, quota/spacing reservation,
   expiry/recovery, persistent history and one claimed in-app summary strip.
   Include sign-out/revocation tests before enabling any real in-app dispatch.
3. **3c — Full scheduling:** relative/fixed rules, item/summary snooze,
   dismiss/off, overdue repeats and all cancellation/catch-up cases. Retain the
   same evaluator/outbox rather than a second path for scheduled mode.

Across these steps:
- Add Reminders history and restrained in-app strips, next-run state and
  settings pause/off. Remove any legacy reminder paths still present.
- Use saved server grants for scheduling; integrate sign-out/password reset,
  deletion and re-enrollment. Keep the installation secret out of JS.
- Tests with fake clock: restart/lease recovery, repeated tick/no duplicates,
  two tabs claiming one strip, 100 items in one minute, multiple rooms under
  one cap, overnight quiet periods/DST, cap reset without burst, mode/rule
  edits, outage catch-up, snooze replacement/coalescing, completion/date clear/
  deletion, unrelated edit, done→active, revoked enrollment and offline logout.
  Test migration and prune→tick without replay; same-day 429→success consumes
  one slot; cross-day retry must respect the new day's cap;
  shutdown leaves ambiguous work recoverable; fixed reminders survive a due
  change without a second identity and completion→uncheck restores only future
  unsent fixed reminders. No network calls under DB lock.
- **Done:** configurable reminders work while using the app, survive reloads
  and restarts, and neither browsing nor snoozing affects another installation.
  No promise of phone delivery yet.

### Stage 4 — Phone notifications

**Integration depends on:** reviewed stage 3 and the approved Web Push design.
Independent transport/security foundations may start under the sequencing
refinement above; secret provisioning and real sends remain rollout work.
**Unblocks:** stage 5.

- Add VAPID sender, installation subscription storage, supported/denied/install
  enrollment UI, explicit test send, disable/resubscribe and endpoint cleanup.
  Reuse the stage-3 outbox, rules and caps; do not create a second reminder
  scheduler just for push. Reconcile subscriptions on foreground return;
  feature-detect subscription-change support rather than relying on it alone.
- Extend the existing worker with visible push and click handling, compatible
  declarative payload/fallback and optional best-effort app icon badges.
  If worker/subscription rotation changes the endpoint, transfer ownership
  within the same installation; do not duplicate room enrollments or replay
  accepted occurrences. Site-data deletion requires fresh enrollment.
- Tests: mocked 2xx/429/404/410/5xx/timeouts and VAPID error; endpoint validation,
  ownership/CSRF/auth revocation and private-data leakage; explicit permission
  gesture and denial; iPhone install guidance; generic/detailed payloads;
  every push shows, including empty/malformed/unrecognized JSON with a generic
  root-link fallback; tap/click allowlist and authentication; no duplicate
  foreground strip; worker upgrades/offline regression; opt out one of several
  rooms; retry expiry and provider acceptance distinct from delivery.
- **Done:** standards-based push is implemented and deterministically tested
  without real external sends. Report genuine physical-device delivery as
  unverified unless actually observed; do not equate desktop WebKit or mocked
  pushes with iPhone lock-screen acceptance.

### Stage 5 — Finish, operational controls and review package

**Depends on:** stage 4 (or stage 3 for choice 3B).
**Unblocks:** owner review, not automatic integration/deployment.

- Review the complete flow at mobile sizes: simple first screen, advanced
  discovery, previews, busy/error states, keyboard, screen-reader labels,
  touch targets, contrast and persistent access to reminder actions.
- Finish safe diagnostics: last scheduler tick, queued/failed counts and
  configuration health, with no endpoint/token/payload leaks. A scheduler fault
  is visible and logged but does not turn an otherwise usable list app into
  a failed healthcheck/restart loop. No new telemetry vendor or dashboard.
- Document operational switches, VAPID provisioning/rotation, Serverless off,
  limits, failed subscription recovery and restore behavior. Before a database
  restore, pause sending; when resuming, suppress pre-restore occurrences so
  restored outbox rows cannot replay old notifications. Keep this within the
  existing backup/deploy workflow, not an extra rehearsal/staging requirement.
- Update `docs/due-date-reminders.md`, affected API contracts, installation,
  offline and deployment guides, and authoritative `ARCHITECTURE.md` once the
  approved architecture is implemented. Keep research in background docs.
- Run full checks below, review the final diff/change stack and provide a
  stage-by-stage behavior/checks/limitations report. No new GitHub issues/PR,
  feature bookmarks, remote cleanup or launch of another agent unless asked.
- **Done:** owner receives reviewable work and honest platform limitations.
  Integration/deploy remain explicit gates. No routine pre-deploy phone check;
  optional real push observation happens only with owner consent and does not
  replace automated evidence.

## Verification and execution contract

Once implementation is explicitly approved, the receiving agent should read
this plan, scope, architecture and current jj state again. Start its own new
workspace from the then-current baseline; do not reuse the planning workspace
or disturb parked `groups`. Shared plans/backlog stay on the docs desk under
explicit ownership. No speculative bookmark moves or remote actions.

For every affected stage, add tests alongside the behavior and run targeted
checks first. Before completion, use the repository's full quality gates:

- Python changes: `uv run ruff format .`, `uv run ruff check --fix .`,
  `uv run pytest -q`, then `uv run ruff format --check .`,
  `uv run ruff check .`, `uv run ty check`.
- Frontend: in `frontend/`, `npm run format`, `npm run lint`, `npm run check`,
  `npm run test`, `npm run build` with the repository's Node setup.
- Browser suite: `uv run pytest browser_tests -q -n 4` across Chromium,
  Firefox and WebKit. Extend/run relevant Android emulator coverage using its
  [guide](../docs/android-emulator-testing.md) if the new UI affects it.
- Fake clock, fake sender, disposable databases and test VAPID keys only.
  Never enroll a real phone or call a real push provider from the test suite.
  Desktop tests validate contracts, not actual APNs/FCM/OS background delivery.

Runtime integration advances after each predecessor's review/tests pass;
independent foundation lanes follow the narrow exceptions above. The owner
can review the approved batch together at the end. If a material new privacy,
architecture, spending or product decision appears, stop at that seam, record
it here and ask; ordinary implementation details do not require a new interview.
Do not move `integration` for feature work or `main` without the applicable
approval. Planning-doc commits have only the existing docs-desk permission.

## Planning ownership and delivery record

- Parent: Pi session `01a1a2c7-22c9-71e2`, coordination workspace
  `/home/hsa/projects/list_app`; sole writer of this plan, research report and
  the existing reminder backlog entry (wording/link only; no queue move).
- Agent-managed investigation workspace `tmp-reminder-plan` at
  `/home/hsa/projects/tmp-reminder-plan` was verified empty, forgotten and
  removed after research. It ran no app/server. Future implementation needs
  its own workspace and the README's
  [new-workspace setup](../README.md#new-jj-workspace).
- Read-only research workflow `0180b8ca-c0a0-444e-acbc-26756b565b4c` completed.
  Platform child `b85062b5-6a6a-4686-9267-089c97c78c39` and UX child
  `c486494a-64ba-4d59-a4dc-ae352d23d057` used Claude Haiku 5.5/high.
  Findings were reviewed and durable evidence moved into the research report.
  No child workspace, writes, notifications or descendants.
- Read-only Haiku/high review `10843a14-b720-4dcd-a53c-3ba441bf4ba5` completed.
  Parent clarified fixed-time identity, stored UTC, pruning/watermarks, quota
  reuse, shutdown, timezone data and stage-3 internal steps. Some findings
  repeated already-added text; an unsupported suggestion to change the browser
  worker count was rejected in favor of the repository's documented `-n 4`.
- GPT-6.1 Terra/high follow-up `6813d59d-0964-4d31-8dd3-5bd537137978`
  completed read-only and found no remaining blockers. Parent additionally
  clarified cross-day retry quota accounting. All children are complete;
  none edited code, spawned descendants or gained integration authority.
- Planning result: change `nkxxqrql` (with ownership setup in `prykkzux`).
  Checks: local Markdown paths/anchors, whitespace/fences, five stage headings,
  stage-3 substeps, explicit authority marker and docs-only diff boundary.
  Runtime suites not run: no application/test code changed. Investigation
  workspace removed; only the coordination workspace remains.
- Recorded owner answers: **A/A/A**. Implementation/architecture authority:
  **granted for all five stages** by the owner's 2026-11-03 request. Lead and
  Conductor ownership is recorded above and in the five linked batch records.

## Progress

### Existing implementation

- [x] Original list-open and room-wide toasts approved on 2026-11-02.
- [x] Original behavior implemented; current contract remains in the linked doc.

### This planning task

- [x] Research competitor UX and current phone-platform constraints.
- [x] Draft configurable behavior, architecture, stages and consolidated choices.
- [x] Independently review the plan and validate planning documents.
- [x] Record final planning change/checks and remove the investigation workspace.

### Approved delivery — in progress

- [x] Owner records choices and explicit implementation/architecture approval.
- [x] Stage 1: quiet due center (reviewed and integrated into the isolated
  delivery line; [verification evidence](../docs/background/reminder-delivery-verification.md#s1-reviewed-integration--2026-11-04)).
- [x] Stage 2: personal policies, dates and previews (reviewed and integrated
  into the isolated delivery line; [verification evidence](../docs/background/reminder-delivery-verification.md#s2-reviewed-integration--2026-11-04)).
- [x] Stage 1 on `integration` (2026-11-05, owner approved; not deployed).
- [x] S1/S2 owner polish: [batch P](batches/reminders-polish.md) reviewed.
- [ ] Owner UX fix: [batch P2](batches/reminders-polish-2.md), started 2026-11-05 (S2 only; settings polish moved to S3).
- [ ] Stage 3: on hold (owner, 2026-11-05). Reviewed parts and resume points:
  `/home/hsa/projects/reminders-archive/` (`resume-points.md`, S3 runtime
  records incl. `OWNER-SUMMARY.md`). All S3 workspaces removed; commits kept.
- [ ] Stage 4: on hold.
- [ ] Stage 5: on hold.
- [ ] Owner review/acceptance; deployment separately approved when requested.
