# Reminders P: S1/S2 UX polish

Lifecycle: temporary

## Brief — frozen at handoff

**Outcome:** Owner-approved (2026-11-05) clarity polish of the due bell and
reminder settings on the reviewed S2 line. Not a new scheduling model and not a
broad UI rewrite. Owner revisits the UX after seeing it.

1. **Clear item action in the bell.** Drop the repeated second-line
   "Reminders" text. The per-item control that opens private settings must say
   what it does (e.g. a labelled icon button). Keep touch size, accessible
   name and keyboard use.
2. **Contextual bell scope.** Room page: whole room with list names. List page:
   that list only, no "Whole room" switch. Keep share restrictions, buckets,
   counts, focus and item/list policy actions.
3. **Explain modes.** Short explanation of Quiet / Daily summary / Scheduled /
   Custom. Show summary time only where it applies. Make the existing custom
   rules editor easy to find. Keep safety controls and real
   enrollment/save/retry semantics.
4. **24-hour time.** HH:MM everywhere for due/reminder time inputs and
   displays, independent of browser locale (native time inputs follow locale,
   so storing HH:MM alone is not enough). No AM/PM, no format setting.
5. **Europe/Oslo default.** New setup defaults to Europe/Oslo (CET/CEST). No
   free-text zone field on the primary screen. Keep real IANA support
   underneath. Never strip other saved zones, reinterpret saved zones or
   confirmed `due_at`, or re-resolve unchanged anchors. Keep explicit
   zone-change safeguards and date-only behavior.

**Scope/seams:** `frontend/src/lib/list/DueCenter.svelte`,
`frontend/src/lib/reminders/ReminderSettings.svelte`, the policy editor,
`frontend/src/lib/list/ItemDialog.svelte`, date/time helpers, their tests and
affected docs. Server changes only if a default truly needs one.

**Exclusions:** S3–S5 behavior, deployment, held-bookmark moves, real pushes,
new dependencies.

**Escalate to Lead:** anything that would change saved data semantics, the
scheduling model or share/privacy boundaries.

**Done:** five items implemented with tests; fresh independent review;
frontend `npm run lint`, check, unit, build; relevant mobile/a11y browser
tests, then one `TZ=UTC uv run pytest browser_tests -q -n 4`; six Python
checks if Python changed.

## Assignment

- Conductor: Pi session named `reminders-polish-list-app`, GPT-6.1 Sol/medium.
  Report to Lead (intercom).
- Workspace: `tmp-reminders-polish`, `/home/hsa/projects/tmp-reminders-polish`,
  created by Lead from reviewed S2 `kwqutmso` / `3f536353`. Lead integrates it
  into `tmp-reminder-delivery` and removes it.
- Children: Conductor may create its own jj child workspaces. All
  implementation and review subagents use `openai/gpt-6.1-terra:medium`.

## Status

Review-ready; accepted by Lead for delivery-line integration. Final tip
`wlwznqly` / `174beac4`; entry workspace clean on empty child `sxqrnqwu`.
Conductor `01a1aa85-90f0-7405-a7cd-5ccfc7a1b965` is idle and available.

Conductor-created children `tmp-polish-bell`, `tmp-polish-time-settings`,
`tmp-polish-share-check` and read-only `tmp-polish-baseline-check` were forgotten
and removed after reachability/cleanliness and evidence checks. All workers and
reviewers finished; effective Terra/medium verified. Lead retains
`tmp-reminders-polish` lifecycle and delivery-line integration.

## Closeout

Delivered all five polish items, preserving saved zones, confirmed anchors,
private enrollment/save/retry semantics and share restrictions. Described stack:
`ynqmrokk` (bell), `lnnlolwq` (settings/time), `xxvrrzww` (test migration),
`nwzluzlq` and `rsqptosy` (review fixes), `wlwznqly` (share-test confirmations).
The last change fixes an ambiguous repeated-toast assertion and adds a two-reset
rotation regression; no share application behavior changed.

Evidence retained outside `/tmp` at
`/home/hsa/projects/reminders-polish-evidence/`:
- Independent reviews: `bell-review-shell.md`, `settings-review*.md`,
  `final-integration-review.md`, `share-fix-review.md`. Initial shell-less review
  was rejected; subsequent reviewers were shell-capable, read-only and not authors.
- Final combined checks: frontend lint/check, 1,113 unit tests and build; all six
  Python checks including 1,792 tests. Logs `final2-*`.
- Final full UTC browser suite: **600 passed**, 798.70 seconds;
  `final2-browser-full.log`, traces/logs under `browser-final2/`. Combined share
  suite also passed all 27 engine cases; mobile/a11y coverage ran before the full suite.
- Earlier evidence remains: focused run had 202 passes and two WebKit sign-in
  failures; first full run had 595 passes and two WebKit failures (revalidation
  timeout, duplicate reset-toast locator). All four passed isolated reruns.
  Requested five repetitions on P and S2 each: both sign-in tests and revalidation
  passed 5/5 on each tree; share test passed 4/5 P versus 5/5 S2 before its fix,
  then 5/5 after. Logs `repeat-{p,s2}-*.log` and `share-fix/`; failures are not
  erased or labelled proven pre-existing. First focused attempt hit a 200-second
  command timeout; the complete run and reruns are retained separately.

Limits: no physical phone keyboard, OS notification, deployment or production
checks; no new dependencies, bookmarks, pushes or port 8080 use. npm reported
16 existing audit findings. S3 is intentionally absent: Lead must preserve its
history/privacy-invalidation hooks when merging overlapping components. No
outstanding product decision; no permission to deploy implied.
