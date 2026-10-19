# ListR UX and visual design review

Scope: read-only review of `frontend/src` (UI, list, room, routes), `app.css`, `app.html`, and the docs named in the brief. No project files were changed.

## Evidence and limits

- Screenshots (390x844, DPR 2, Chromium emulation, light and dark): `/tmp/claude-1000/-home-hsa-projects-list-app/ebd66c47-eac2-409f-8636-07295fea0317/scratchpad/shots/`
  - `01_room_light.png`, `02_list_light.png`, `03_check_toast_light.png`, `04_options_light.png`, `05_filter_dairy_light.png`, `06_item_dialog_light.png`, `07_list_menu_light.png`, `08_typing_suggestions_light.png`, `09_list_dark.png`, `10_offline_pill.png`
- Measured sizes come from Chromium emulation, not iOS.
- **The built app is stale.** `frontend/build` dates from 2026-10-18 10:29 and has no Sort control. The Options screenshot therefore lacks Sort. Sort findings come from code only.
- The connection pill (reconnecting or saving) was not captured. Offline shows the banner instead. The pill overlap is from CSS geometry.
- Contrast ratios are computed from the token values in `app.css`. Scripts: `scratchpad/contrast.py`.
- Server on port 8095 was started for the test and stopped afterwards.

## Contrast check (WCAG 2.x)

Light mode:
- Text on surface 14.8:1. Muted text on surface 5.4:1. Primary button text 5.2:1.
- Danger text 5.6:1. Warning text 5.0:1. Toast success text 5.1:1.
- Control border on surface 3.7:1 (3:1 needed for UI edges, passes).
- Focus ring on page 4.7:1.
- Tag colors as text: lowest is tag-2 red at 4.56:1 on the page background, 4.98:1 on surface. All pass 4.5:1.

Dark mode:
- Text on surface 13.3:1. Muted text on surface 6.5:1. Primary text on surface 5.0:1.
- Danger text on surface 4.6:1 (thin margin).
- Control border on surface 3.5:1 (passes).
- Tag-4 purple on surface 4.55:1 (thin margin).

Verdict: colors pass. The issues are not contrast. They are tag letters and tag color meaning (finding 4).

## Measured tap targets (Chromium, 390px)

| Element | Size (px) | Target |
| --- | --- | --- |
| Item row | 358 x 37 | 44 tall (suggested) |
| Checkbox hit area | 44 x 36 | 44 x 44 |
| Item name button | 196 x 36 | 44 tall |
| Tag letter (per row) | 26 x 26 | 44 |
| Tag chip (filter) | 69 x 36 | 44 |
| Toast Undo | 61 x 32 | 44 |
| Toast dismiss | 44 x 32 | 44 |
| Options (text button) | 97 x 44 | ok |
| List menu (dots) | 44 x 44 | ok |
| Add button | 64 x 44 | ok |
| Quantity +/- (code: ItemRow.svelte:237-240) | 20 x 28 | 44 |

## Taps for common tasks (current app)

- Open a list from a remembered room: 1 tap (the room page lists it).
- Add an item: 1 tap on the field, type, Enter. The field keeps focus.
- Check off: 1 tap. Undo: 1 tap within 5 s.
- Edit name, notes, date or quantity: 2 or more taps (name, edit, Save).
- Change quantity: 3 taps (name, +, Save), or 3 taps to turn on "Show quantities" first (Options, switch, Done).
- Delete an item: 2 taps (name, trash), or 2 taps from Options mode. Undo exists.
- Tag an item: 1 tap on a 26 px letter.
- Filter by tag: 1 tap per chip. Clearing takes 1 tap per chip; there is no clear-all.
- Sort: 4 taps (Options, select, choice, Done).
- Hide checked items: 3 taps (Options, switch, Done), plus mode and number.
- Share a list: 2 taps (dots, Share List), then the phone sheet.
- Dark mode: 2 taps (dots, Dark mode).
- Add a list tag: 3 taps plus typing (Options, field, Enter, Done).

## Ranked findings

Impact and effort are my estimates. Risk means the chance of breaking an existing rule or behavior.

### 1. Enter adds what is typed, even when the user meant to search (high impact, S to M)

- Evidence:
  - `AddItem.svelte:83-86`: Enter adds `text` unless a suggestion is highlighted. "mil" becomes an item.
  - `ListView.svelte:84-88`: typing filters the list only for an offline or unconfirmed view. Online it only suggests, up to 3 names (`items.ts:26`).
  - Screenshot `08_typing_suggestions_light.png`: typing "m" shows "milk" as a suggestion, and the list does not filter.
- Impact: accidental junk items. The field means two things (add and search), and search works differently online and offline.
- Proposal:
  - Option A (small): Enter adds only when the typed text matches no item. Otherwise it picks the first suggestion. Show "Add 'mil'?" for the rest.
  - Option B (medium): separate a Search mode from Add. Search always filters the list. Add is a button and a clear action.
- Effort: S for A, M for B.
- Risk: changes a documented decision in `ARCHITECTURE.md` ("Major UX decisions": the add field creates, leaves, or unchecks). Needs your approval.

### 2. Checked items jump to the bottom at once (high impact, S)

- Evidence: `ListView.svelte:88-90` sorts on every change, so a tap moves the row. `items.ts` and `docs/item-sorting.md` put checked items below open ones. Screenshot `02_list_light.png` shows the moved rows.
- Impact: the next row slides under the thumb. Fast checking causes mis-taps.
- Proposal: keep the tapped row in place until about 1.5 s after the last tap, or until the next refresh. Then move it with `animate:flip`.
- Effort: S. Risk: low. Ordering rule in the docs stays the same.

### 3. Tap targets are below 44 px in the hot paths (high impact, S to M)

- Evidence:
  - Row height 36 px: `ItemRow.svelte:135-137` (measured 37).
  - Quantity +/-: 20 x 28 px, `ItemRow.svelte:237-240`.
  - Tag letters: 26 x 26 px, `ItemRow.svelte:273-284`.
  - Filter chips: 36 px, `ListTags.svelte:146-148`.
  - Toast buttons: 32 px, `Toast.svelte:143-149` (Undo measured 61 x 32).
  - Radio labels and count field: 36 px, `HideDoneSettings.svelte:147` and `:176`.
  - Sort select: 36 px, `ListOptions.svelte:67`.
- Impact: misses on the checkbox and on Undo.
- Proposal: keep the look, grow the hit area. Use padding or a `::before` overlay to reach 44 px. Keep the 36 px row only if the checkbox hit area is 44 px tall.
- Effort: S to M. Risk: density changes if the row grows.

### 4. Tag letters collide, and tag colors shift (high impact on clarity, S)

- Evidence:
  - "Dairy" and "Dry goods" both show "D" (screenshot `02_list_light.png`).
  - Color is by position in the sorted tag list: `ItemRow.svelte:106`, `ListTags.svelte:86`, `tags.ts:10-12`. Adding or deleting a tag recolors the others.
  - Color is the only cue between "D" blue and "D" green. Color-blind users may not tell them apart.
- Proposal: derive the color from a hash of the tag name, so it stays stable. Show a second letter or an icon when letters collide. Show the full name on tap of the chip.
- Effort: S. Risk: a hash can give two tags the same color. Check with the existing `app-colors.test.ts`.

### 5. Controls sit in the top reach zone (medium to high impact, L, bold)

- Evidence:
  - Back, Options and the dots are all at the top: `ListHeader.svelte:28-41`, `ListMenu.svelte:88-111`.
  - The add field is sticky at the top: `AddItem.svelte:149-154`.
  - Only the undo toasts sit at the bottom: `Toast.svelte:73-101`.
  - On large phones the top right is hard to reach one-handed.
- Proposal (bold): a bottom bar with the add field above the keyboard, and buttons for Options, Tags, Sort and the dots. The header keeps the title and back link.
- Effort: L. Risk: medium. Layout, keyboard, offline banner and sticky rules change. Test in all three browsers and the Android emulator.

### 6. Options mixes settings with edit mode (medium to high impact, M)

- Evidence:
  - Options shows the settings card, "Add Tag", and × on every tag: `ListOptions.svelte`, `ListTags.svelte:60-106`.
  - Options also shows a red trash on every row: `ListView.svelte:266`, `ItemRow.svelte:119-129`.
  - Delete is immediate, with a 5 s undo: `ListView.svelte:197-208`.
- Impact: a user who opens settings may tap a trash button. Opening Options changes the whole list.
- Proposal: split into two things. "Edit" mode shows trash, tag × and "Add tag". Settings (sort, quantities, hide checked) live in a sheet or the dots menu.
- Effort: M. Risk: low.

### 7. Sort is buried (medium impact, S)

- Evidence: 4 taps, in the Options panel, as a native select: `ListOptions.svelte:33-39`. The shipped build lacks it, so this is code evidence only.
- Proposal: a small "Sort: A to Z" button next to the list title, or a segmented row.
- Effort: S. Risk: low.

### 8. A toast for every check, stacked at the bottom (medium impact, S)

- Evidence:
  - Every check makes an info toast with Undo: `ListView.svelte:125-134`, `items.ts:56-58`.
  - Up to 3 toasts stay 4 to 5 s: `toasts.svelte.ts:29-31`, `undo-toast.ts`.
  - Screenshot `02_list_light.png` shows three stacked toasts covering about 110 px at the bottom.
- Proposal: no toast when checking. The checkbox already shows the state. Use one undo bar that replaces the previous one. Keep the toast for deletes.
- Effort: S. Risk: low. Undo stays available.

### 9. Tag filter: no clear-all, no summary, lost on leave (medium impact, S)

- Evidence: `ListTags.svelte:146-159`, `ListView.svelte:79-81` and `:151-155`. Filter state is component state. Screenshot `05_filter_dairy_light.png` shows only the chip fill as a cue.
- Proposal: an "All" or "Clear" chip, a line "Showing: Dairy and Meat", and keep the filter per list for the session.
- Effort: S. Risk: low.

### 10. Quantity editing costs 3 taps and tiny buttons (medium impact, S to M)

- Evidence: the stepper shows only when "Show quantities" is on (`ItemRow.svelte:78-98`). Otherwise editing means name, +, Save (`ItemDialog.svelte:72-93`). The +/- buttons are 20 x 28 px.
- Proposal: tap the "×2" badge to step, or long-press the row. Show the stepper by default.
- Effort: S to M. Risk: low.

### 11. Offline banner takes about 160 px at the top (medium impact, S)

- Evidence: `SavedViewNotice.svelte:31-36` and styles `:41-50`. Screenshot `10_offline_pill.png` shows three lines pushing the header and list down. It is not sticky.
- Proposal: one short line, for example "Offline. 1 change waiting." Put it in the status pill.
- Effort: S. Risk: low.

### 12. Connection pill sits over the header title and Options (medium impact, S, not captured)

- Evidence:
  - `ConnectionStatus.svelte:41-52`: fixed at top 0.4rem, centered, up to 10rem wide, z-index 20.
  - `ListHeader.svelte:47-56`: header is 44 px at top 0, and holds the title and Options.
  - By geometry the pill spans about x 115 to 275 px. Options spans about x 230 to 327 px. They overlap.
- Proposal: place the status inside the header or at the bottom.
- Effort: S. Risk: low. Verify with a screenshot in the reconnecting state first.

### 13. No empty state for a new list (medium impact on first use, S)

- Evidence: `ListView.svelte:282-284` shows a message only when a filter hides everything. An empty list shows nothing.
- Proposal: "No items yet. Type above to add."
- Effort: S. Risk: none.

### 14. Checked items have no group label (low to medium, S)

- Evidence: checked rows sit below with strikethrough only (`02_list_light.png`).
- Proposal: a divider "Checked (3)". Optional collapse.
- Effort: S. Risk: low.

### 15. Item editor is a centered modal, Save sits mid-screen (medium impact, M)

- Evidence: `Dialog.svelte:89-98` (width min(100% - 2rem, 24rem), centered). `ItemDialog.svelte:53-60`. Save sits near 68% of the screen height (screenshot `06_item_dialog_light.png`). The notes field may be covered by the keyboard.
- Proposal: a bottom sheet on phones.
- Effort: M. Risk: low.

### 16. Room list rows put rename and delete side by side (medium impact, S)

- Evidence: `RoomLists.svelte:84-101`. Delete (trash) sits next to rename (pencil). A confirm exists, but the layout invites a mis-tap.
- Proposal: move delete into the rename dialog, or into an overflow menu.
- Effort: S. Risk: low.

### 17. Item names are forced to lowercase (medium impact, M, decision needed)

- Evidence: `ARCHITECTURE.md` "Major UX decisions" says item names are stored in lowercase. `items.ts:28-31` lowercases on add. "iPhone charger" shows as "iphone charger".
- Proposal: keep the typed casing for display, and match duplicates without case. Needs a data step.
- Effort: M. Risk: medium. This is an architecture decision. You should decide.

### 18. Type scale is not tokenized (low to medium, S)

- Evidence: about 12 font sizes in use: `app.css:112` (1.3rem), `app.css:286` (1.1rem), `RoomHeader.svelte:41` (1.5rem), `ListHeader.svelte:74` (1.25rem), `Dialog.svelte:109` (1.15rem), `ItemRow.svelte:210` and `:261` (0.875rem), `ItemRow.svelte:219` and `:282` (0.8rem), `SavedViewNotice.svelte:49` (0.9rem), `ConnectionStatus.svelte:63` (0.8rem), `NeedsConnection.svelte:18` (0.8rem).
- Smallest text is 12.8 px: dates, hints, tag letters.
- Page titles vary from 1.25rem to 1.5rem.
- Proposal: five tokens, for example `--text-xs` 0.8125rem, `--text-sm` 0.875rem, `--text` 1rem, `--text-lg` 1.25rem, `--text-xl` 1.5rem. Raise the date to at least 0.875rem.
- Effort: S.

### 19. Spacing is hard-coded (low, S)

- Evidence: `app.css:43-46` defines only `--gap` and `--touch`. Components use 0.25, 0.4, 0.5, 0.65, 0.7 and 0.75rem.
- Proposal: `--space-1` to `--space-5`.
- Effort: S.

### 20. No motion for add, check or reorder (low, S)

- Evidence: `ListView.svelte:263` has no `animate:` or `transition:`. Reduced motion is handled in `app.css:228-234`.
- Proposal: `animate:flip` at 150 ms, and a short fade for new rows. Respect reduced motion.
- Effort: S.

### 21. Dark mode: same icon in both states, and buried (low, S)

- Evidence: `ThemeToggle.svelte:24` uses one icon. `ThemeMenuItem.svelte:19-21` puts the switch in the menu.
- Proposal: a sun icon in dark mode. Or three choices: System, Light, Dark.
- Effort: S.

### 22. Select has no font size (low, S, verify)

- Evidence: `app.css:124-129` resets `font` for button, input and textarea only. `ListOptions.svelte:35` and `:66-69` set no font size. Chromium's default is 13.3 px. My WebKit test returned 16 px, so the iPhone result is not confirmed.
- Proposal: add `select { font: inherit; }`.
- Effort: S. Risk: none. Verify on iPhone before claiming a zoom bug.

### 23. Return key label (low, S)

- Evidence: `AddItem.svelte:108` uses `enterkeyhint="enter"`.
- Proposal: "done" or "send", whichever reads best. Test in iOS only if needed.

### 24. iOS status bar style (low, S, code only)

- Evidence: `app.html:18` sets `black`, which is a dark status bar over the light theme.
- Proposal: use `default` for light and keep `black-translucent` for dark, or leave as is. I have not checked this on a device.

### 25. The app name is missing on room and list pages (low, S)

- Evidence: `ListHeader.svelte:28-33` and `RoomHeader.svelte:20-25`. The back arrow replaces the brand. The brand shows only on the home, share and admin pages.
- Proposal: small brand under the title, or keep as is.

### 26. Admin rows may be cramped (low, S, not screenshotted)

- Evidence: `AdminRooms.svelte:86-107`. A room name, "Reset password" and "Delete" text buttons share a 390 px row.
- Proposal: icon buttons, or move actions into the room view.

### 27. Reset share link sits under Share List (low, S)

- Evidence: `ListMenu.svelte:88-106`. Reset is one tap from Share, with a confirm dialog.
- Proposal: move Reset into the share dialog.

## Bold ideas (ranked by value for five users)

1. Bottom bar with add field and buttons (finding 5). Largest gain in reach. Large effort.
2. Swipe gestures: swipe right to check, left to delete with undo. Keep swipe away from the left screen edge so iOS back-swipe still works. Checkbox and buttons stay as the non-swipe path. Medium to large effort. Risk of accidental swipes while scrolling.
3. Group by tag or aisle: add a "Group by tag" option with section headers. Items with two tags need a rule (first tag, or repeat). Rules go in `docs/item-sorting.md`. Medium effort.
4. Compact and comfortable density: a per-browser setting. Comfortable uses 44 px rows. Compact keeps 36 px. Small to medium effort.
5. New color scheme: the primary blue is generic. A green or warm primary is cheap with the existing tokens in `app.css:14-84`. Re-run `app-colors.test.ts`. Small effort.
6. Haptics: `navigator.vibrate` does not work on iOS Safari, so this helps Android only. Low value for this group.

## Positive notes

- Contrast passes in both modes (see table).
- The add field keeps focus after each add (`AddItem.svelte:77`), so bulk entry is fast.
- Delete and check have undo.
- Header buttons are 44 px.
- Reduced motion is respected.
- Dark mode follows the system.
- Checked items sink to the bottom, and hiding is available.
- No hover-only controls.

## Top 3

1. Fix the add and search field (finding 1). Enter should not create "mil" from a half-typed search. Effort S to M. Needs your approval because it changes a documented decision.
2. Make check-off safe (findings 2, 3 and 8): keep the tapped row in place for about 1.5 s, widen the hit areas to 44 px, and use one undo bar instead of a toast per check. Effort S to M.
3. Make tags readable (finding 4): stable colors from the tag name, and a second letter or icon when letters collide. Effort S.

Bigger step after these: the bottom bar (bold idea 1).

## Items that need your decision

- Finding 1: changing the add-field behavior (`ARCHITECTURE.md` decision).
- Finding 17: lowercase item names (`ARCHITECTURE.md` decision).
- Finding 5: layout change of the header and add field.
