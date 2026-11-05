# Reminders P2 validation

P2 hides the unfinished personal-reminder settings while preserving their code,
API and unit tests. Due dates, times and the bell remain available. Current
behavior and the single switch are documented in [due-date reminders](../due-date-reminders.md).

## Scope and review

- Base: `wlwznqly` (`reminders-s2` at handoff).
- UI and browser tests were implemented by separate Terra/low workers.
- Fresh Sol/high independent review inspected both exact diffs against the base:
  pass, no actionable findings. An earlier Terra/low review lacked sufficient
  tool access and was not used as the final review.
- No server implementation, saved-data rules, dependencies, bookmarks,
  deployment or push changed.

## Checks

- `npm ci`, `npm run lint`, `npm run check`, `npm run build`: passed.
- `npm test`: 1,113 passed, one known baseline timeout. The failing test is
  `offline-integration.test.ts` → “replays an older lowercase add body without
  rewriting its queued op”. Its fixed October 6 queue date is now beyond the
  30-day hold threshold. The failure was reproduced with the unchanged baseline
  frontend. The Lead approved leaving its fix out of P2.
- Focused due-center, phone, private-reminder, policy-editor and timed-offline
  browser files: 69 passed, 120 skipped across Chromium, Firefox and WebKit.
- Full `TZ=UTC uv run pytest browser_tests -q -n 8`: 482 passed, 120 skipped,
  four WebKit sign-in failures and one associated teardown error. All four
  failed cases passed in three serial reruns (12 passes, clean teardown).
  The Lead accepted these as the known WebKit sign-in flakes from earlier work.
- `TZ=UTC uv run pytest -q`: 1,792 passed.
- `uv run ruff format .`, `uv run ruff check --fix .`, followed by format/check
  verification and `uv run ty check`: passed.

## Deliberately paused browser checks

The shipping build has no settings entry points. Tests that need those entry
points remain in source, explicitly skipped until S3 restores them. There is no
special test-only enabled build.

| File | Paused cases across three engines | Still active |
| --- | ---: | --- |
| `test_svelte_private_reminders.py` | 102 | Public-share visitor test, three cases |
| `test_svelte_policy_editor.py` | 18 | None: every test opens settings |

Every skip reason names P2 and says to re-enable in
[S3](../../plans/batches/reminders-s3.md#deferred-polish-from-p2).

## New active coverage

`test_svelte_due_center_phone.py` checks light and dark themes at a 390 px phone
viewport in all three engines. It checks hidden room/list/item/bell entry
points, saved due-time editing, the item name above one metadata row, row touch
size, horizontal overflow, keyboard reveal/focus and public-share isolation.

## Execution artifacts

At owner-requested closeout, gate logs and failed full-browser artifacts were
moved to `/home/hsa/projects/reminders-archive/p2-closeout-2026-11-05/checks/`.
The failed-run evidence is in its `browser-full-temp` directory. Temporary data
from fully passed focused, Python and serial-rerun checks was removed earlier.

The owner accepted P2 (`yvsklvxw`), which is reachable from the accepted
integration change `nnsymyky`. All child runs and owned servers stopped. The
child workspace `reminders-p2-tests` and entry workspace `tmp-reminders-p2`
were forgotten and removed. The Conductor's pane and tab were closed at the
owner's request. The disposable preview database was removed; the shared
`.env` target was left untouched.
