# Room-card test transfer — 9 November 2026

Evidence for **lr-005.1.7**, based on `integration` `6d4b0dcb`.
The lr-4rc planning handoff narrows this work to audit row 3 only.
No unaccepted engine-matrix, tier, helper or product changes are imported.

## Assertion map and removal gate

Candidate: `browser_tests/test_svelte_due_center.py::test_room_card_counts_what_is_due_in_the_list`.
Replacement: `frontend/src/lib/room/RoomLists.test.ts` →
“shows tomorrow's milk as 1 due, not overdue, beside the Groceries link”.

| Old input or check | Faster retained check |
| --- | --- |
| Groceries contains unchecked milk dated tomorrow | The mounted test applies a synthetic full feed through the real `RoomStore.refresh()`: Groceries/milk dated 2026-11-03, real due clock fixed at local noon 2026-11-02, store status `ready`. |
| Count is in the same `li.list-row` as the Groceries link | The mounted real `RoomLists` is queried for its Groceries anchor, then its closest `li.list-row`. Both must exist. |
| That row contains `1 due` | That row's real `.due` element must have exactly `1 due`. The real component calls the real `dueTally`; neither is mocked. |
| That row does not contain `overdue` | The complete row text must not contain `overdue`. A second list contains overdue dishes, so an accidental room-wide tally also fails. |
| API date write/feed and date classification | Existing `tests/test_item_date.py::test_edit_sets_a_date` and `test_date_is_in_the_changes_feed`; `frontend/src/lib/list/due-reminders.test.ts` → `dueTally` “counts unchecked overdue, today and tomorrow items only”. |

The old sign-in/create/add/date-dialog steps prepare the fixture. Their helper
checks (room ready, list URL/heading, cleared add field, closed date dialog)
are shared setup, not a unique security or native-input test in this body.
They still run in retained due-center journeys, including the grouping smoke.
The date-only native input/reload test remains untouched. This transfer does
not claim happy-dom tests real navigation, native date input, CSS layout,
server persistence, IndexedDB, offline behavior, authorization or an engine.
Three boundaries are stubbed: `goto`, the `changes` feed source and the
optional enrollment network read. The synthetic feed replaces network/API
integration, not store processing. Enrollment returns `not_enrolled`, leaving
the real device-zone fallback in place.

**Removal gate passed before deletion.** Independent Astra/medium review
`a58d6024` returned **FAIL** for the missing feed-stub disclosure, not a
coverage gap. After correction, follow-up `3ea617ab` returned **PASS** and
explicitly approved removal of this body on all three engines. Only then was
the body removed. Final fresh-context diff review is recorded below.
Keep all storage, offline, security and engine-specific tests and all four
three-engine smokes. No skips, retries, waits or timeout changes are allowed.

## Counts and checks

Exact collection lists and `count-proof.json` are saved privately under
`.night-evidence/lr-005.1.7/`. Every count change is explained here.

| Suite | Before → after | Explanation |
| --- | --- | --- |
| Python | 1,792 → 1,792 | Exact node sets equal. |
| Browser | 606 → 603; 202 → 201 per engine | Only this body × Chromium/Firefox/WebKit removed; zero additions. AST comparison proves every remaining body, import and helper is unchanged. |
| Frontend listed bodies | 566 → 567 | Only the new mounted case added; no removals. |
| Frontend runtime cases | 1,114 → 1,115 | Baseline runtime count from lr-005.1.1; final execution passes all 1,115. No new full baseline run. |
| Four three-engine smokes | 12 → 12 | Exact node sets equal, all engines retained. |

- Old Chromium candidate: **1 passed**, 6.84 s command, 6.774 s JUnit case.
- New mounted test plus existing due-reminder file: **15 passed**, zero failures.
  The mounted case took **36.626 ms**, including its fixture and cleanup.
- Required Python checks passed: Ruff format, safe lint fixes, final format/lint
  checks, `ty`, full pytest **1,792 passed**, no skips (48.98 s after deletion).
  A preceding quality run also passed 1,792 before the deletion.
- Frontend lint, type/component check (zero warnings), full tests **1,115 passed**
  and build passed in the unchanged host zone, **Europe/Oslo**. Historical UTC
  failures are not repaired or claimed passing. No retry or zone override used.
- Retained grouping smoke and native date/save/reload/clear, all three engines:
  **6 passed**, no skips, 17.36 s, four workers under the machine-wide lock.
  These are focused retained checks, not the whole browser suite.
- npm reports 16 existing audit findings; no dependency or lockfile change.
- Final fresh-context Astra/medium review `d715e4c0`: **PASS**, no findings;
  independent agreement with this map and the exact removal. Both review
  contexts had their effective model/tier verified through native status.
- No product, helper, engine, skip, retry, timeout, plan, backlog or release-gate
  changes. Android and the full browser suite were not run.

The old case and new case costs use different runners and scopes. They show
that this is a cheap transfer, not measured full-suite elapsed savings. The
historical post-matrix estimate was about six gross worker-seconds; do not
add the matrix's savings again. No broad baseline or speed claim is made.

## Cases kept for the owner

Audit rows 11–13 remain unchanged: native date/save/reload/clear;
suggestion count labels plus viewport/wrap/focus; reload with no due toast.
Recommend **keep all three**. Faster helpers do not cover those browser checks.
Audit rows 1–2 and 4–10 also remain: they lack reviewed mounted UI coverage
and are outside this one-transfer pilot. No wider cleanup is requested here.
