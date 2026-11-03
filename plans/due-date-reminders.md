# Due-date reminders

Lifecycle: tracked

Research and staged redesign planning are selected (owner, 2026-11-03).
Implementation, architecture changes and deployment are not approved.
The original sketch below will be expanded into a handoff-ready plan.

## Planning ownership

- Owner: Pi session `01a1a2c7-22c9-71e2` in `/home/hsa/projects/list_app`
  (shared docs desk; sole writer of this plan and the task's research report).
- Agent-managed investigation workspace: `tmp-reminder-plan`, at
  `/home/hsa/projects/tmp-reminder-plan`, based on `integration`.
- Bounded read-only children: phone-platform research and reminder UX research.
  They may search official sources, but may not edit files, spawn children,
  change version control, subscribe devices or send notifications.
- Status: research in progress. Parent reviews sources and writes the plan;
  owner reviews the recommendation and consolidated decisions before coding.
- Completion: commit planning documents only, retain the existing backlog
  placement, resolve children and remove the investigation workspace.
  No feature acceptance or production changes.

## Options

Ordered from easiest to hardest. Each builds on the one before.

### 1. Toast when a list opens

- When a list loads, check its item dates and show a toast, such as "2 items
  due tomorrow".
- Frontend only. No server work and no permissions.
- Limit: you see it only when you open that list.

### 2. Warning anywhere in the app

- Check dates across all lists, so the toast shows whichever list is open.
- Re-check every few minutes, so "due in 1 hour" appears while the app is open.
- Still an in-app toast, not a phone notification. Browsers pause timers in
  background tabs, so it is unreliable there.

### 3. Phone notification when the app is closed (Web Push)

- The user taps "Turn on reminders". The browser asks for permission and gives
  a push address for that device.
- The server stores the address. A scheduled job (every 15 minutes or so) finds
  items due soon and sends a message through Apple's or Google's push service.
- The phone wakes the service worker, which shows the notification.
- Android (Chrome): works, even without installing the app.
- iPhone (iOS 16.4+): works only for the home-screen app, and permission must
  be asked from a button tap. Not in normal Safari.
- No server-free route: Notification Triggers was dropped, and Periodic
  Background Sync is Chrome-only and unreliable.
- New parts: a push library (such as `pywebpush`), VAPID keys, a table for
  device push addresses, a scheduled job on Railway, an on/off setting and
  duplicate-reminder protection. This changes the architecture; update
  [`ARCHITECTURE.md`](../ARCHITECTURE.md) if chosen.

## Open questions

- What counts as "soon"? A fixed rule (due today or tomorrow) or a reminder
  time per item?
- Do options 1 and 2 cover enough, or is option 3 needed?
- For option 3: who gets the reminder in a shared room? Every device that
  turned reminders on?

## Suggested path

Ship options 1 and 2 together as one small step. Plan option 3 separately, and
try it on Android first.

## Progress

- [x] Options 1 and 2 chosen; "soon" is due today or tomorrow, overdue included (owner, 2026-11-02). Option 3 is in Later.
- [x] Options 1 and 2 implemented; current behavior in [due-date reminders](../docs/due-date-reminders.md).
- [ ] Option 3 questions (who gets the reminder in a shared room)
- [ ] Write the implementation plan for option 3
