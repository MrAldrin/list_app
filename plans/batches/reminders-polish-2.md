# Reminders P2: bell and item-dialog UX fix

Lifecycle: temporary

## Brief — frozen at handoff (owner split, 2026-11-05)

**Outcome:** Make stage 2 ready to integrate. Stage 2 shows due times and the
due bell; its personal reminder settings send nothing until stage 3. So this
batch polishes only what users see now, and hides the settings until stage 3
ships. Polish of the settings screens moved to the
[S3 brief](reminders-s3.md#deferred-polish-from-p2).

1. **Hide personal reminder settings until stage 3.** Hide every entry point:
   room menu "Personal reminders" and "Personal room reminder policy", list
   "Personal list reminders", item dialog "Personal reminders for this item",
   and the per-item settings action in the bell. Use one clearly named switch
   so stage 3 can turn them back on. Keep the components, API and their
   unit tests; do not delete code. Due times stay visible and editable.
2. **Bell rows on phone width.** Item names now wrap one letter per line. Use
   two lines: item name on line one; list name, date and status on line two.
   Keep touch size, keyboard use and existing bucket/scope behavior.
3. **Plain language** in what stays visible (bell, due date/time in the item
   dialog): no "policy", "enrollment", "phase" or similar.
4. **Phone-width checks.** Browser tests at a phone viewport, in the existing
   three engines, that fail if bell item names wrap per letter or actions
   overflow. Light and dark themes. Plus a test that the hidden entry points
   are absent.

**Scope/seams:** `DueCenter.svelte`, `ItemDialog.svelte`, `ListView.svelte`,
`RoomMenu.svelte`, their tests and affected docs. Frontend only.

**Exclusions:** settings-screen polish (moved to S3), S3–S5 behavior, server
changes, deployment, bookmark moves, new dependencies, jj cleanup of parked
lines.

**Escalate to Lead:** anything changing saved data, privacy/share boundaries,
or a browser test that cannot stay meaningful once settings are hidden.

**Done:** four items with tests; fresh independent review; `npm run lint`,
check, unit, build; focused reminder/settings browser files plus the new
phone-width tests in three engines; then one full
`TZ=UTC uv run pytest browser_tests -q -n 8`; owner checks the refreshed
preview.

## Assignment

- Lead: Pi session `01a1ace3-fba8-774e-bb47-66e3583fc2af` (coordination
  workspace). Report there via intercom.
- Conductor: Pi `reminders-p2-list-app`, GPT-6.1 Sol/medium. It may do heavy
  lifting itself. Prefer subagents on `openai/gpt-6.1-terra` low; if one fails
  or falls short, retry on `openai/gpt-6.1-sol` high, or do it directly.
  Independent review is still required.
- Workspace: `tmp-reminders-p2`, `/home/hsa/projects/tmp-reminders-p2`, new
  from `reminders-s2` (`wlwznqly`). Conductor creates, owns and removes it after
  integration.

## Status

Started by the owner, 2026-11-05.

## Closeout

(Conductor writes here.)
