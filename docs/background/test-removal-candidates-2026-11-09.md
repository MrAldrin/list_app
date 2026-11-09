# Test removal candidates — 9 November 2026

Read-only audit for **lr-005.1.3**, based on `integration` `6d4b0dcb`.
**No tests changed. No immediate deletions are justified.** The ranked table
has 13 candidates. Most rule tests already exist; most UI replacements do not.

## Decision and limits

- **Meets the rule: none today.** The owner's rule in **lr-005.1.7** requires
  full API/frontend assertion coverage, agreement from a second independent
  agent, and no security, offline, storage or engine-specific protection.
  This audit has no independent reviewer. A source scout is not that review.
- **Needs owner / not yet eligible:** rows 1–10 can become eligible without
  a new policy decision: add the specified lower-layer checks first, then
  obtain independent map approval in lr-005.1.7. Keep each browser body until
  both steps pass. Rows 11–13 need an explicit owner choice; recommend keeping
  them. No decision blocks completion of this audit.
- Reuse **lr-gt2.1**, with implementation owned by **lr-gt2.6**: do not propose
  its engine cuts again or count their savings here. Its timed-due exception
  stays on three engines until **lr-gt2.4** is fixed. Preserve the four named
  three-engine smokes. No release-gate or test-cadence decision is made here.
- Prefer small additions to existing test fixtures. Do not build a large
  component harness merely to save two worker-seconds. Cheap Python/frontend
  tests are not deletion priorities; Android has no measured cost or mapped
  replacement. Offline, native storage, access/revocation, Unicode-engine,
  live-stream and stale-write journeys are excluded from automatic removal.

## Cost basis and reading key

Reused the **lr-005.1.1** inventory (`psqyoumn` / `d534316e`,
`docs/background/test-inventory-2026-11-09.md`) and the engine matrix and speed
report at **lr-gt2-checkpoint** (`slworksn` / `37fa7e55`):
`engine-matrix-review-2026-11-08.md`, `browser-suite-speed-2026-11-08.md`.
These files are on their task lines, not this base. Read them with
`jj file show -r <bookmark> docs/background/<file>`.
Also reused the [runtime report](../reports/test-suite-runtime-2026-11-05.md),
[review](test-suite-review.md) and [speed history](test-suite-speed.md).

**Old / marginal** below is measured old three-engine worker-s / **estimated
additional gross worker-s freed after the approved matrix**, rounded from the
old Chromium case. XML `time` includes setup, call and teardown. Source:
`/home/hsa/projects/list_app/.night-evidence/overnight-2026-11-06/partial-tests/evidence/browser-baseline.xml`.
No new timing run. These are selection estimates, **not elapsed-time or net
savings**. Replacement-test time must be subtracted; measure it in lr-005.1.7.
For an unchanged three-engine body, marginal uses all three cases. Toast-helper
changes make old add-count cost especially stale (row 9). Do not sum rows
across alternatives or add the matrix's Firefox/WebKit savings again.

Current-test prefixes below mean `browser_tests/test_svelte_<prefix>.py`.
Faster-file names mean `frontend/src/lib/` plus the given path; Python paths
start with `tests/`. **Existing** checks remain; **add** checks do not exist yet.
Ranks balance confidence, replacement effort and marginal cost, not old cost
alone. Risk flags: **S** security, **O** offline, **T** native browser storage,
**I** input/events, **E** engine behavior. “I only” means no S/O/T/E assertion
was found in that body; it does not exempt the new map from review.

## Needs owner / not yet eligible — rule-compatible after the stated work

All actions below mean **move to frontend, then delete the old browser body
only after the removal rule passes**. Keep API checks and browser smokes.

| Rank | Current test | Old-to-retained assertion map and missing replacement | Old / marginal worker-s | Risk; confidence |
| ---: | --- | --- | ---: | --- |
| 1 | `items::test_add_trims_python_whitespace` | U+0085-wrapped input → `Added Oat Milk` toast and the sole row `Oat Milk`. **Existing:** `list/items.test.ts` → `normalizeItemName` “trims while keeping the display capitalization”; `addFeedback` texts; `tests/test_api_name_case.py::test_item_add_uses_python_strip_whitespace`. **Add:** mounted AddItem→ListView test sends that exact input through submit, asserts the normalized callback, toast and row. Pure helper tests alone do not prove the submit wiring. | 6.40 / ~2.0 | I only; high rule overlap, medium replacement confidence |
| 2 | `tags::test_tap_filters_the_items` | Chip click → `aria-pressed=true`, only milk; second click → bread and milk. **Existing:** `list/tags.test.ts` → `filterByTags` one-tag/no-tag cases; `list/visible-items.test.ts` → “keeps only the items with every chosen tag”. **Add:** mounted ListView/ListTags click→filter→render assertions, including order. The retained `items::test_tags_filter_and_hide_done` also exercises this browser path; that overlap alone does not meet the faster-layer rule. | 19.80 / ~6.0 | I only; medium; this test uses click, not touch/drag |
| 3 | `due_center::test_room_card_counts_what_is_due_in_the_list` | Tomorrow's milk → `1 due` beside Groceries, no `overdue`. **Existing:** `list/due-reminders.test.ts` → `dueTally` “counts unchecked overdue, today and tomorrow items only”. **Add:** mounted RoomLists test with a fixed day and ready room data; assert the correct list row contains `1 due` and no `overdue`. The tally test does not check placement or copy. | 22.26 / ~6.1 | No S/O/T/I/E assertion; medium; existing due suite has known red timezone cases |
| 4 | `items::test_empty_list_hint_and_clear_tag_filter` | Empty hint shown, absent after add; Clear absent with no filter; selecting Lidl leaves milk; Clear hides itself and restores apple/milk. **Existing:** `list/visible-items.test.ts` empty-list/tag cases; `list/tags.test.ts` no-filter behavior. **Add:** mounted ListView state changes and ListTags Clear callback→parent reset→render checks, including hint and Clear presence. Do not replace the parent reset with a callback spy only. | 19.55 / ~6.0 | I only; medium |
| 5 | `items::test_tag_colors_stay_and_letters_differ` | Dairy/Dry goods buttons show Da/Dr; adding Aisle leaves Dairy's letters and inline `--tag` value unchanged. **Existing:** `list/tags.test.ts` → `tagLetters` “shows two letters when two tags share the first letter”, plus `tagColor` name/order stability. **Add:** mounted ItemRow with those tags, then updated list tags; assert both labels and unchanged inline CSS property. This test does not inspect computed color or layout. | 8.14 / ~2.3 | No S/O/T/I/E assertion; medium; do not extend this proposal to visual theme tests |
| 6 | `tags::test_edit_item_tag_chips_light_up_at_once` | Edit Item: click Lidl on, Market on, Lidl off; each pressed state changes at once; Cancel keeps Market on and Lidl off in the row. **Existing:** `data/overlay.test.ts` → “sets a tag to the wanted state, and toggles only without one”; `tests/test_api_tag_ops.py::test_toggle_item_tag_on_and_off`. **Add:** extend `list/ItemDialog.test.ts` and a ListView fixture with live item updates; assert chip states, immediate tag callbacks, and Cancel does not undo them. Its one existing test checks hidden reminder controls, not these events. | 8.79 / ~2.3 | I only; medium |
| 7 | `tags::test_new_tags_come_from_options_not_the_tag_row` | Initially no Tags row or New tag button; Options→Tags addition gives exactly one Lidl chip and a Lidl item-tag button. **Existing:** `tests/test_api_tag_ops.py::test_tag_add` checks trimmed add and feed; `list/tags.test.ts` → `newTag`. **Add:** mounted ListView/ListOptions/TagsDialog integration checks entry point, absence checks, submit and updated row/item buttons. A test of `newTag` alone misses all UI placement checks. | 7.67 / ~2.0 | I only; medium; low saving if a new fixture is costly |
| 8 | `tags::test_one_tag_mode_asks_first_and_keeps_the_first_tag` | Confirm appears for two tags; Cancel closes it and leaves single-mode off; confirm closes flow, sets mode on, leaves Lidl pressed and Market unpressed on milk. **Existing:** `list/tags.test.ts` → `single-mode tag rules`; `data/overlay.test.ts` → “strips extra tags from items when the list switches to single mode”; `tests/test_api_tag_settings.py::test_switching_to_single_keeps_the_first_tag_in_list_order`. **Add:** TagsDialog→parent/store→ItemRow component test for confirm, cancel, mode state and final tag buttons. Keep real dialog-focus tests elsewhere. | 9.28 / ~2.5 | I only; medium; no focus/native-dialog assertion in this body |
| 9 | `times_added::test_item_dialog_counts_adds_and_unchecks` | Dialog shows Added once and a Last added timestamp; Cancel hides it; list row omits Added once; successful check/uncheck responses precede reopen; checking keeps once, unchecking changes to Added 2 times. **Existing:** `list/items.test.ts` → `addedLabel`, `lastAddedLabel`; `data/add-count.test.ts` → check/uncheck cases; `tests/test_times_added.py` → new/check/uncheck API cases. **Add:** ItemDialog/ItemRow rendering and ListView check→reopen sequence, including close and row absence. Labels plus reducers do not cover this assembly. | 50.86 / ~2–4, low confidence | I only; medium map, low cost confidence; helper report has Chromium call ~1.1 s, not the old ~15 s |
| 10 | `due_center::test_reveal_of_a_missing_item_says_so` | Navigate to the list with `?item=no-such-item&at=1` → missing-item status visible. **Existing:** `list/reveal.test.ts` only parses/encodes the URL; no missing-item UI test. **Add:** ListView route-state integration with a ready store and absent UID; assert the status text after processing that URL. This must exercise the URL→component effect, not just `readReveal`. Keep successful reveal/focus browser tests. | 6.87 / ~1.9 | I (URL) only; medium-low; defer if route mocking needs broad harness work |

## Needs explicit owner decision — low-confidence cuts; keep by default

| Rank | Current test | Candidate action and old-to-retained assertion map | Old / marginal worker-s | Risk and recommendation |
| ---: | --- | --- | ---: | --- |
| 11 | `item_date::test_item_date_is_saved_shown_and_cleared` | **Move to frontend/API** only by owner choice: Save closes dialog and displays 20 Oct; reload keeps it; reopened date field is 2026-10-20; Clear+Save closes dialog and removes row date. **Existing:** `list/items.test.ts` → `formatItemDate`; `data/item-date.test.ts` → set/null/absent date projection; `tests/test_item_date.py::test_edit_sets_a_date`, `test_edit_null_clears_the_date`. **Missing:** mounted edit/clear/row and fresh server-feed reload assembly. `ItemDialog.test.ts` only proves that the date input exists. | 21.27 / ~21.3 | I/E: native date input and real reload; no offline/native-storage assertion. Keep. Timed-due tests are not an exact date-only Clear replacement. |
| 12 | `items::test_suggestions_rank_by_add_count_and_scroll` | **Move ranking to frontend, merge viewport checks into** `items::test_suggestion_keyboard_tab_and_touch_selection` only with approval. **Existing:** `list/items.test.ts` → `itemSuggestions` ranking. **Must retain:** exact tea e/a/b/c/d count labels, overflowing popup, last option initially outside viewport, ArrowUp wraps/selects/scrolls it into view, field keeps focus. The merge target currently lacks these overflow/wrap assertions. Add them before any deletion; a ranking unit test cannot prove them. | 8.05 / ≤~2.2, less added merge time | I/E: scroll, viewport, keyboard focus. Keep separate unless the merged journey stays clear and cheaper. This is not another engine-cut request. |
| 13 | `due_center::test_reload_shows_no_due_toast` | **Merge into** `due_center::test_bell_counts_overdue_and_today_and_groups_the_panel`: after a reload with a due item, retain bell-visible and zero `.toasts .toast` containing `due`. **Existing:** smoke proves bell/grouping, not reload/no-toast; no lower-layer reload→no-toast check. The comment that toasts were replaced is not an assertion replacement. Add the negative mounted startup/remount check and preserve real reload if merged. The current body does not assert a post-reload due count, so a visible bell alone does not prove due data loaded. | 19.91 / ≤~6.1, less added reload time | E unknown: reload/startup timing; no explicit storage assertion. Low confidence. Keep; a merge alone fails the faster-layer rule and may save little. Do not change the three-engine smoke's engine set. |

## Handoff and checks

Start lr-005.1.7 with small existing-fixture extensions, not wholesale deletion.
Recheck these maps after lr-gt2.6 and tier-marker work; retain all assertions or
leave the old test. Independent reviewer agreement is still required. Record
counts before/after, each removed node, replacement cost and affected-suite
results. No current test is redundant merely because its rule helper is tested.

Document validation: source/test references, XML costs, local links and
single-file scope checked. No product suites ran. The inventory's known red
baselines remain: frontend **1,112 passed / 2 failed** under UTC; archived
browser **484 passed / 2 failed / 120 skipped**. These are input evidence, not
passing checks of this change. No waits, retries, new skips or timeout changes.
No Python files changed, so Python quality checks do not apply to this report.
