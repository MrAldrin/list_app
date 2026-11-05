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

Active — launched 2026-11-05.

## Closeout

(Conductor writes here.)
