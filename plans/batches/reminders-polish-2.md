# Reminders P2: bell and item-dialog UX fix

Lifecycle: temporary

## Brief — frozen at handoff

**Outcome:** Fix the owner-found UX problems in batch P (preview test,
2026-11-05). The screens must read clearly on a phone.

1. **Bell rows on phone width.** Item names wrap one letter per line because the
   full "Reminder settings" text takes most of the row. Use two lines: item name
   on line one; list name, date and status on line two. The per-item settings
   action becomes a compact icon button with an accessible name (e.g. "Reminder
   settings for <item>"). Keep touch size and keyboard use.
2. **Item reminder dialog when this browser is not set up.** Today it shows
   developer text ("phase 2", "enrollment", "policies") and three unclear
   buttons. Instead say it plainly, e.g. "Reminders are off on this device. Turn
   them on to set reminders for this item." with one **Turn on reminders**
   action that opens the existing setup. Show **Try again** only after a real
   load failure, with a plain message.
3. **Plain-language pass** on bell, item dialog and reminder settings: remove
   "policy", "enrollment", "phase" and similar from user-facing text. Keep real
   behavior and privacy rules.
4. **Phone-width checks.** Add browser tests at a phone viewport (and the
   existing three engines) that fail if bell item names wrap per letter or
   actions overflow. Check light and dark themes.

**Scope/seams:** `DueCenter.svelte`, item reminder dialog / `PolicyEditor`,
`ReminderSettings.svelte`, their tests and affected docs. Frontend only.

**Exclusions:** S3–S5 behavior, new settings, deployment, bookmark moves, new
dependencies.

**Escalate to Lead:** anything changing save semantics, privacy/share
boundaries or the setup flow itself.

**Done:** four items with tests; fresh independent review; `npm run lint`,
check, unit, build; focused reminder/settings browser files plus the new
phone-width tests in three engines; owner checks the refreshed preview.

## Assignment

- Conductor: Pi `reminders-polish-list-app`, GPT-6.1 Sol/medium; subagents
  `openai/gpt-6.1-terra:medium`. Report to Lead.
- Workspace: new workspace from accepted P tip `wlwznqly` (now on top of
  `integration`). Conductor to be chosen when the owner starts this batch.

## Status

Not started. A launch on 2026-11-05 was stopped by the owner after one
command; no code was changed and its workspaces were removed. Waits for the
owner's go.

## Closeout

(Conductor writes here.)
