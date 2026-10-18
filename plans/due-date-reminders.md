# Due-date reminders

Lifecycle: tracked

A rough sketch, not an approved plan. Users asked to be warned when an item's
date is close. Dig into the options, pros and cons before choosing.

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

- [ ] Choose options and answer the open questions
- [ ] Write the implementation plan
