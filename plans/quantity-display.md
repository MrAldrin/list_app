# Quantity display on the Svelte list page

Lifecycle: temporary

Fixes the backlog bug: "Show quantities" reset when the page was left.
Svelte only; NiceGUI stays as it is until the switch (Milestone 4).

## Decisions (owner, 2026-10-05)

- A quantity is data, so everyone sees it: a row with quantity 2 or more
  always shows "×2" next to the name, whatever the options say.
- "Show quantities" only adds the − / + stepper on every row. The stepper
  shows the number, so the row then has no "×2".
- "Show quantities" is a personal setting: saved per list in this browser
  (`localStorage`). No database change, no API op. The app has no accounts,
  so "per person" means "per device".
- "Only show minimum 2" is removed; the "×2" badge covers it.

## Steps

1. `items.ts`: drop `onlyAboveOne`; a helper for the "×2" badge; unit tests.
2. Save and load "Show quantities" per list in `localStorage` (safe when
   storage is blocked); unit tests.
3. `ItemRow` shows the badge; `ListOptions` loses the second switch.
4. Browser test: badge without the option; the setting survives a reload.
5. Update decision 84, remove the backlog item, delete this plan.

## Progress

- [ ] 1 Badge helper
- [ ] 2 Saved setting
- [ ] 3 UI
- [ ] 4 Browser test
- [ ] 5 Docs, backlog, plan removed
